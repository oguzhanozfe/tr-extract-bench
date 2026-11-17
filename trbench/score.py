"""Type-aware field scoring.

Rules (also in the README):
- Gold is always the clean canonical value. A missing key in the prediction counts as null.
- str/enum: compared after a Turkish-aware fold (İ/I/ı -> i, ş->s, ğ->g, ü->u, ö->o, ç->c),
  lowercasing and dropping punctuation, so matching ignores diacritics and "A.Ş." == "AŞ".
- tax_office: as str, ignoring a trailing "V.D." / "Vergi Dairesi".
- id: uppercase, spaces/dots/dashes removed.
- amount/number/int: parsed with Decimal from numbers or strings in Turkish or English format
  ("1.234,56 TL", "1234.56", "%20"); amounts must match to the cent.
- date: parsed from ISO, dd.mm.yyyy, dd/mm/yyyy, "17 Kasım 2026" (also ascii / English months).
- Invalid JSON (after removing <think>/<thought> blocks and one ``` fence) scores every gold field as a false negative.
"""
import datetime as dt
import json
import re
from decimal import Decimal, InvalidOperation

from .docs import SCHEMAS

FOLD = str.maketrans({"İ": "i", "I": "i", "ı": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u",
                      "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c", "â": "a", "Â": "a", "î": "i", "û": "u"})
MONTHS = {}
for i, names in enumerate([("ocak", "january", "jan"), ("subat", "february", "feb"), ("mart", "march", "mar"),
                           ("nisan", "april", "apr"), ("mayis", "may"), ("haziran", "june", "jun"),
                           ("temmuz", "july", "jul"), ("agustos", "august", "aug"), ("eylul", "september", "sep"),
                           ("ekim", "october", "oct"), ("kasim", "november", "nov"), ("aralik", "december", "dec")]):
    for n in names:
        MONTHS[n] = i + 1


def fold(s) -> str:
    s = str(s).translate(FOLD).lower()
    s = re.sub(r"[^\w\s]", "", s)
    return " ".join(s.split())


def norm_id(s) -> str:
    return re.sub(r"[\s.\-]", "", str(s)).upper()


def parse_decimal(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    s = re.sub(r"(?i)\b(tl|try|kg)\b|[₺%\s]", "", str(v))
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_date(v):
    s = str(v).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
        if m:
            d, mo, y = map(int, m.groups())
        else:
            m = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", fold(s))
            if not m or m.group(2) not in MONTHS:
                return None
            d, mo, y = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def match(ftype: str, pred, gold) -> bool:
    if ftype in ("str",) or ftype.startswith("enum"):
        return fold(pred) == fold(gold)
    if ftype == "tax_office":  # "Meram", "Meram V.D." and "Meram Vergi Dairesi" are the same office
        strip = lambda x: re.sub(r"\b(vd|vergi dairesi( mudurlugu)?)$", "", fold(x)).strip()
        return strip(pred) == strip(gold)
    if ftype == "id":
        return norm_id(pred) == norm_id(gold)
    if ftype == "date":
        return parse_date(pred) == parse_date(gold)
    p, g = parse_decimal(pred), parse_decimal(gold)
    if p is None or g is None:
        return False
    tol = Decimal("0.005") if ftype == "amount" else Decimal("0.0001")
    return abs(p - g) <= tol


def parse_output(text):
    """Return a dict or None. Reasoning tags and one ``` fence are removed; nothing else is repaired."""
    s = re.sub(r"<(think|thought)>.*?</\1>", "", text or "", flags=re.S).strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, re.S)
    if m:
        s = m.group(1)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def is_null(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in ("", "null", "none", "yok", "n/a"))


def score_item(doc_type: str, gold: dict, output: str) -> dict:
    schema = SCHEMAS[doc_type]
    pred = parse_output(output)
    r = {"json_valid": pred is not None, "tp": 0, "fp": 0, "fn": 0, "halluc": 0, "emitted": 0}
    if pred is None:
        r["fn"] = sum(1 for name, _, _ in schema if gold[name] is not None)
        return r
    names = {name for name, _, _ in schema}
    extra = [k for k in pred if k not in names and not is_null(pred[k])]
    r["halluc"] += len(extra)
    r["fp"] += len(extra)
    r["emitted"] += len(extra)
    for name, ftype, _ in schema:
        g, p = gold[name], pred.get(name)
        if is_null(p):
            if g is not None:
                r["fn"] += 1
            continue
        r["emitted"] += 1
        if g is None:
            r["fp"] += 1
            r["halluc"] += 1
        elif match(ftype, p, g):
            r["tp"] += 1
        else:
            r["fp"] += 1
            r["fn"] += 1
    return r


def aggregate(items: list) -> dict:
    t = {k: sum(i[k] for i in items) for k in ("tp", "fp", "fn", "halluc", "emitted")}
    p = t["tp"] / (t["tp"] + t["fp"]) if t["tp"] + t["fp"] else 0.0
    r = t["tp"] / (t["tp"] + t["fn"]) if t["tp"] + t["fn"] else 0.0
    return {"n": len(items), "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "json_valid": sum(i["json_valid"] for i in items) / len(items) if items else 0.0,
            "halluc_rate": t["halluc"] / t["emitted"] if t["emitted"] else 0.0}
