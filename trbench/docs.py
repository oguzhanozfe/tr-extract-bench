"""Synthetic Turkish business documents with exact ground truth, plus noise variants.

A document is built once as a list of blocks (lines of segments) together with its
gold JSON. Noise variants only change how the blocks are rendered to text; the
gold values never change. Segment kinds:
  ("label", key)  a field label, rendered TR / EN / mixed and OCR-noised
  ("t", text)     literal prose, OCR-noised
  ("v", text)     a value, never OCR-noised (only the ascii variant folds it)
"""
import datetime as dt
import random
from decimal import Decimal, ROUND_HALF_UP

from . import ids

VARIANTS = ["clean", "ocr", "ascii", "mixed", "reordered", "ocr_values", "distractors"]
HARD_VARIANTS = ["ocr_values", "distractors"]  # added after the first tier saturated
DOC_TYPES = ["invoice", "bank_statement", "kap_disclosure", "cargo_notice"]
MARKER = "*** SENTETİK ÖRNEK BELGE - gerçek değildir / SYNTHETIC TEST DOCUMENT ***"

LABELS = {
    # invoice
    "t_invoice": ("e-FATURA", "E-INVOICE"),
    "seller": ("Satıcı", "Seller"),
    "vkn": ("VKN", "Tax ID"),
    "tckn": ("TCKN", "National ID"),
    "tax_office": ("Vergi Dairesi", "Tax Office"),
    "buyer": ("Alıcı (Sayın)", "Buyer"),
    "invoice_no": ("Fatura No", "Invoice No"),
    "invoice_date": ("Fatura Tarihi", "Invoice Date"),
    "due_date": ("Son Ödeme Tarihi", "Due Date"),
    "items": ("Mal/Hizmet | Miktar | Birim Fiyat | Tutar", "Item | Qty | Unit Price | Amount"),
    "subtotal": ("Mal Hizmet Toplam Tutarı", "Goods/Services Subtotal"),
    "vat": ("Hesaplanan KDV", "Calculated VAT"),
    "total": ("Ödenecek Tutar", "Amount Payable"),
    "pay_iban": ("Ödeme IBAN", "Payment IBAN"),
    # bank statement
    "t_statement": ("HESAP EKSTRESİ", "ACCOUNT STATEMENT"),
    "bank": ("Banka", "Bank"),
    "holder": ("Hesap Sahibi", "Account Holder"),
    "iban": ("IBAN", "IBAN"),
    "period": ("Ekstre Dönemi", "Statement Period"),
    "overdraft": ("KMH Limiti", "Overdraft Limit"),
    "opening": ("Devreden Bakiye", "Opening Balance"),
    "tx": ("Tarih | Açıklama | Tutar | Bakiye", "Date | Description | Amount | Balance"),
    "credits": ("Toplam Alacak", "Total Credits"),
    "debits": ("Toplam Borç", "Total Debits"),
    "closing": ("Dönem Sonu Bakiye", "Closing Balance"),
    # kap
    "t_kap": ("ÖZEL DURUM AÇIKLAMASI", "MATERIAL EVENT DISCLOSURE"),
    "company": ("Şirket Unvanı", "Company Title"),
    "ticker": ("Borsa Kodu", "Ticker"),
    "disc_date": ("Açıklama Tarihi", "Disclosure Date"),
    "subject": ("Konu", "Subject"),
    # cargo
    "t_cargo": ("KARGO GÖNDERİ BİLDİRİMİ", "SHIPMENT NOTIFICATION"),
    "carrier": ("Kargo Firması", "Carrier"),
    "tracking": ("Takip No", "Tracking No"),
    "sender": ("Gönderici", "Sender"),
    "receiver": ("Alıcı", "Recipient"),
    "address": ("Teslimat Adresi", "Delivery Address"),
    "ship_date": ("Gönderi Tarihi", "Ship Date"),
    "eta": ("Tahmini Teslim", "Estimated Delivery"),
    "weight": ("Ağırlık", "Weight"),
    "pieces": ("Parça Sayısı", "Pieces"),
    "cod": ("Kapıda Ödeme Tutarı", "Cash on Delivery"),
    "status": ("Durum", "Status"),
}

# Field schema per document type: (name, type, description). Types drive scoring.
SCHEMAS = {
    "invoice": [
        ("invoice_no", "id", "e-fatura number"),
        ("invoice_date", "date", "invoice date"),
        ("due_date", "date", "payment due date, null if not stated"),
        ("seller_name", "str", "seller company title"),
        ("seller_vkn", "id", "seller tax ID (VKN, 10 digits)"),
        ("seller_tax_office", "tax_office", "seller tax office (vergi dairesi) name"),
        ("buyer_name", "str", "buyer name or company title"),
        ("buyer_id", "id", "buyer VKN or TCKN"),
        ("subtotal", "amount", "total before VAT"),
        ("vat_rate", "number", "VAT rate in percent, e.g. 20"),
        ("vat_amount", "amount", "VAT amount"),
        ("total", "amount", "amount payable including VAT"),
        ("payment_iban", "id", "IBAN for payment, null if not stated"),
    ],
    "bank_statement": [
        ("bank_name", "str", "bank name"),
        ("account_holder", "str", "account holder name"),
        ("iban", "id", "account IBAN"),
        ("period_start", "date", "statement period start"),
        ("period_end", "date", "statement period end"),
        ("opening_balance", "amount", "opening balance"),
        ("closing_balance", "amount", "closing balance"),
        ("total_credits", "amount", "sum of incoming amounts"),
        ("total_debits", "amount", "sum of outgoing amounts, as a positive number"),
        ("overdraft_limit", "amount", "overdraft (KMH) limit, null if not stated"),
    ],
    "kap_disclosure": [
        ("company_name", "str", "disclosing company title"),
        ("ticker", "id", "stock ticker (borsa kodu)"),
        ("disclosure_date", "date", "disclosure date"),
        ("disclosure_type", "enum:Yeni İş İlişkisi|Kâr Payı Dağıtımı|Pay Geri Alımı|Yönetim Kurulu Değişikliği",
         "subject of the disclosure"),
        ("counterparty", "str", "other party of a contract, null if none"),
        ("amount", "amount", "main monetary amount in TL, null if none"),
        ("effective_date", "date", "date the event takes effect or is paid, null if none"),
    ],
    "cargo_notice": [
        ("carrier", "str", "cargo company"),
        ("tracking_no", "id", "tracking number"),
        ("sender_name", "str", "sender name"),
        ("receiver_name", "str", "recipient name"),
        ("receiver_city", "str", "recipient city (il)"),
        ("ship_date", "date", "ship date"),
        ("estimated_delivery", "date", "estimated delivery date, null if not stated"),
        ("weight_kg", "number", "weight in kg"),
        ("pieces", "int", "number of pieces"),
        ("cod_amount", "amount", "cash-on-delivery amount, null if not stated"),
        ("status", "enum:Teslim Edildi|Dağıtımda|Transfer Merkezinde|Şubede Bekliyor", "shipment status"),
    ],
}

# Fictional name parts. Combinations are random; any match with a real entity is coincidental.
COINED = ["Ilgazkaya", "Mavitepe", "Akyelken", "Sarıdereli", "Gökbora", "Tunçdağ", "Beyazkumlu",
          "Ladinova", "Çınaraltı", "Karaçamlı", "Yeşilvadi", "Durugöl", "Kızılsu", "Ayçiçekli"]
SECTORS = ["Tekstil", "Gıda", "Lojistik", "Yazılım", "Enerji", "İnşaat", "Makine", "Kimya", "Mobilya"]
SUFFIXES = ["San. ve Tic. A.Ş.", "Ltd. Şti.", "A.Ş.", "Tic. Ltd. Şti."]
FIRST = ["Ayşe", "Mehmet", "Zeynep", "Mustafa", "Elif", "Ahmet", "Şule", "İbrahim", "Gülşen", "Çağrı",
         "Özge", "Ömer", "Işıl", "Ilgın", "Ümit", "Gökçe"]
LAST = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Öztürk", "Aydın", "Arslan", "Doğan", "Kılıç",
        "Güneş", "Erdoğdu", "Işıkçı", "Ünal"]
BANKS = [("Örnekbank A.Ş.", "90001"), ("Kurgu Katılım Bankası", "90002"),
         ("Deneme Yatırım Bankası", "90003"), ("Sentez Bank T.A.Ş.", "90004")]
CARRIERS = ["Örnek Kargo", "Kurgu Ekspres", "Deneme Lojistik Kargo", "Sentez Taşımacılık"]
TAX_OFFICES = ["Kadıköy", "Beşiktaş", "Çankaya", "Konak", "Nilüfer", "Seyhan", "Meram", "Üsküdar"]
CITIES = [("İstanbul", "Ataşehir"), ("Ankara", "Çankaya"), ("İzmir", "Bornova"), ("Bursa", "Osmangazi"),
          ("Antalya", "Muratpaşa"), ("Eskişehir", "Tepebaşı"), ("Şanlıurfa", "Haliliye"),
          ("Muğla", "Bodrum"), ("Çanakkale", "Merkez"), ("Iğdır", "Merkez")]
STREETS = ["Atatürk Cad.", "Çiçek Sok.", "Gül Sok.", "İnönü Bulvarı", "Şehitler Cad.", "Lale Sok."]
PRODUCTS = ["Pamuklu kumaş (metre)", "Danışmanlık hizmeti", "Yazılım lisansı", "Çelik profil",
            "Ambalaj kolisi", "Zeytinyağı 5 lt", "Bakım-onarım hizmeti", "Ofis sandalyesi"]
TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
             "Ekim", "Kasım", "Aralık"]

ASCII_MAP = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iIsSgGuUoOcCaAiIuU")
OCR_CONFUSIONS = {"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c", "İ": "I", "l": "1",
                  "o": "0", "O": "0", "m": "rn", "e": "c", "a": "o", "S": "5", "B": "8", "i": "l",
                  "g": "q", "n": "ri", "t": "f"}

CENT = Decimal("0.01")


def money(rng, lo, hi) -> Decimal:
    return (Decimal(rng.randint(lo * 100, hi * 100)) / 100).quantize(CENT)


def fmt_num(d: Decimal, decimals=2) -> str:
    """Turkish format: 1.234,56"""
    neg = d < 0
    s = f"{abs(d):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if neg else "") + s


def fmt_money(d: Decimal, style: int) -> str:
    n = fmt_num(d)
    return [f"{n} TL", f"{n} ₺", f"TL {n}", f"{n} TRY"][style]


def fmt_date(d: dt.date, style: int) -> str:
    return [f"{d:%d.%m.%Y}", f"{d:%d/%m/%Y}", f"{d.day} {TR_MONTHS[d.month - 1]} {d.year}"][style]


def rand_date(rng, start=dt.date(2025, 1, 1), days=640) -> dt.date:
    return start + dt.timedelta(days=rng.randint(0, days))


def company(rng) -> str:
    return f"{rng.choice(COINED)} {rng.choice(SECTORS)} {rng.choice(SUFFIXES)}"


def person(rng) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def kv(key, value):
    return [("label", key), ("t", ": "), ("v", value)]


class Doc:
    """Blocks: list of (movable, [line, ...]); line = list of segments."""

    def __init__(self, title_key):
        self.blocks = [(False, [[("label", title_key)], [("t", MARKER)]])]

    def add(self, *lines, movable=True):
        self.blocks.append((movable, list(lines)))


def gen_invoice(rng):
    ms, ds = rng.randrange(4), rng.randrange(3)
    seller, buyer_is_person = company(rng), rng.random() < 0.4
    buyer = person(rng) if buyer_is_person else company(rng)
    buyer_id = ids.make_tckn(rng) if buyer_is_person else ids.make_vkn(rng)
    inv_date = rand_date(rng)
    due = inv_date + dt.timedelta(days=rng.choice([15, 30, 45])) if rng.random() < 0.6 else None
    iban = ids.make_iban(rng, rng.choice(BANKS)[1]) if rng.random() < 0.5 else None
    rate = rng.choice([1, 10, 20, 20])
    prefix = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVYZ") for _ in range(3))
    inv_no = f"{prefix}{inv_date.year}{rng.randint(1, 999999):09d}"
    items, subtotal = [], Decimal(0)
    for name in rng.sample(PRODUCTS, rng.randint(1, 4)):
        qty, unit = rng.randint(1, 40), money(rng, 15, 4000)
        line = (unit * qty).quantize(CENT)
        subtotal += line
        items.append([("t", name + " | "), ("v", f"{qty} | {fmt_num(unit)} | {fmt_num(line)}")])
    vat = (subtotal * rate / 100).quantize(CENT, ROUND_HALF_UP)
    total = subtotal + vat
    office = rng.choice(TAX_OFFICES)

    seller_vkn = ids.make_vkn(rng)
    d = Doc("t_invoice")
    d.add(kv("seller", seller), [("t", "  "), ("label", "tax_office"), ("t", ": "), ("v", f"{office} V.D.")],
          [("t", "  "), ("label", "vkn"), ("t", ": "), ("v", seller_vkn)])
    d.add(kv("buyer", buyer), [("t", "  "), ("label", "tckn" if buyer_is_person else "vkn"), ("t", ": "),
                               ("v", buyer_id)])
    d.add(kv("invoice_no", inv_no))
    d.add(kv("invoice_date", fmt_date(inv_date, ds)))
    if due:
        d.add(kv("due_date", fmt_date(due, ds)))
    d.add([("label", "items")], *items)
    d.add(kv("subtotal", fmt_money(subtotal, ms)))
    d.add([("label", "vat"), ("t", " (%"), ("v", str(rate)), ("t", "): "), ("v", fmt_money(vat, ms))])
    d.add(kv("total", fmt_money(total, ms)))
    if iban:
        d.add(kv("pay_iban", ids.group4(iban)))
    gold = {"invoice_no": inv_no, "invoice_date": inv_date.isoformat(),
            "due_date": due.isoformat() if due else None, "seller_name": seller, "seller_vkn": seller_vkn,
            "seller_tax_office": office, "buyer_name": buyer, "buyer_id": buyer_id,
            "subtotal": str(subtotal), "vat_rate": str(rate), "vat_amount": str(vat), "total": str(total),
            "payment_iban": iban}
    return d, gold


def gen_bank_statement(rng):
    ms, ds = rng.choice([0, 3]), rng.randrange(3)
    bank, code = rng.choice(BANKS)
    holder = person(rng) if rng.random() < 0.5 else company(rng)
    iban = ids.make_iban(rng, code)
    start = rand_date(rng).replace(day=1)
    end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    opening = money(rng, 500, 250000)
    overdraft = Decimal(rng.choice([5000, 10000, 25000, 50000])) if rng.random() < 0.4 else None
    bal, credits, debits, rows = opening, Decimal(0), Decimal(0), []
    days = sorted(rng.sample(range(0, (end - start).days + 1), rng.randint(3, 7)))
    for day in days:
        if rng.random() < 0.45:
            amt = money(rng, 100, 60000)
            desc = rng.choice([f"EFT Gelen - {person(rng)}", "Maaş Ödemesi", f"Havale Gelen - {company(rng)}"])
            credits += amt
        else:
            amt = -money(rng, 20, 15000)
            desc = rng.choice(["POS Harcama - MARKET", "Fatura Ödemesi - Elektrik", f"Havale Giden - {person(rng)}",
                               "Kredi Kartı Ödemesi", "Fatura Ödemesi - Doğalgaz"])
            debits -= amt
        bal += amt
        rows.append([("v", fmt_date(start + dt.timedelta(days=day), 0) + " | "), ("t", desc),
                     ("v", f" | {fmt_num(amt)} | {fmt_num(bal)}")])

    d = Doc("t_statement")
    d.add(kv("bank", bank))
    d.add(kv("holder", holder))
    d.add(kv("iban", ids.group4(iban)))
    d.add([("label", "period"), ("t", ": "), ("v", f"{fmt_date(start, ds)} - {fmt_date(end, ds)}")])
    if overdraft is not None:
        d.add(kv("overdraft", fmt_money(overdraft, ms)))
    d.add(kv("opening", fmt_money(opening, ms)))
    d.add([("label", "tx")], *rows)
    d.add(kv("credits", fmt_money(credits, ms)))
    d.add(kv("debits", fmt_money(debits, ms)))
    d.add(kv("closing", fmt_money(bal, ms)))
    gold = {"bank_name": bank, "account_holder": holder, "iban": iban, "period_start": start.isoformat(),
            "period_end": end.isoformat(), "opening_balance": str(opening), "closing_balance": str(bal),
            "total_credits": str(credits), "total_debits": str(debits),
            "overdraft_limit": str(overdraft.quantize(CENT)) if overdraft is not None else None}
    return d, gold


def gen_kap(rng):
    name = rng.choice(COINED)
    comp = f"{name} {rng.choice(SECTORS)} {rng.choice(['A.Ş.', 'San. ve Tic. A.Ş.'])}"
    ticker = name.translate(ASCII_MAP).upper()[:4] + rng.choice(["", "X", "Q"])
    ddate = rand_date(rng)
    kind = rng.choice(["Yeni İş İlişkisi", "Kâr Payı Dağıtımı", "Pay Geri Alımı", "Yönetim Kurulu Değişikliği"])
    eff = ddate + dt.timedelta(days=rng.randint(3, 60))
    ms = rng.randrange(4)
    cp, amount, eff_out = None, None, eff
    if kind == "Yeni İş İlişkisi":
        cp, amount = company(rng), money(rng, 1_000_000, 900_000_000)
        prose = [("t", "Şirketimiz ile "), ("v", cp), ("t", " arasında toplam "), ("v", fmt_money(amount, ms)),
                 ("t", " (KDV hariç) bedelli tedarik sözleşmesi "), ("v", fmt_date(eff, 2)),
                 ("t", " tarihinde imzalanmıştır. Sözleşme süresi 24 aydır.")]
    elif kind == "Kâr Payı Dağıtımı":
        amount = money(rng, 5_000_000, 400_000_000)
        prose = [("t", "Yönetim Kurulumuz, 2025 yılı kârından toplam "), ("v", fmt_money(amount, ms)),
                 ("t", " brüt nakit kâr payının "), ("v", fmt_date(eff, 2)),
                 ("t", " tarihinde dağıtılmasını Genel Kurul'un onayına sunmaya karar vermiştir.")]
    elif kind == "Pay Geri Alımı":
        amount = money(rng, 10_000_000, 500_000_000)
        eff_out = None
        prose = [("t", "Yönetim Kurulumuz, piyasa koşulları dikkate alınarak pay geri alım programı başlatılmasına "
                       "ve program için azami "), ("v", fmt_money(amount, ms)),
                 ("t", " fon ayrılmasına karar vermiştir. Program süresi en fazla 3 yıldır.")]
    else:
        prose = [("t", "Yönetim Kurulu Üyemiz "), ("v", person(rng)),
                 ("t", " görevinden istifa etmiş olup, boşalan üyeliğe "), ("v", fmt_date(eff, 2)),
                 ("t", " tarihinden itibaren geçerli olmak üzere "), ("v", person(rng)),
                 ("t", " atanmıştır.")]

    d = Doc("t_kap")
    d.add(kv("company", comp))
    d.add(kv("ticker", ticker))
    d.add(kv("disc_date", fmt_date(ddate, rng.randrange(2))))
    d.add(kv("subject", kind))
    d.add(prose, movable=False)
    d.add([("t", "Yukarıdaki açıklamalarımızın, Sermaye Piyasası Kurulu düzenlemelerine uygun olduğunu beyan "
                 "ederiz.")], movable=False)
    gold = {"company_name": comp, "ticker": ticker, "disclosure_date": ddate.isoformat(), "disclosure_type": kind,
            "counterparty": cp, "amount": str(amount) if amount is not None else None,
            "effective_date": eff_out.isoformat() if eff_out else None}
    return d, gold


def gen_cargo(rng):
    ds = rng.randrange(3)
    carrier = rng.choice(CARRIERS)
    tracking = str(rng.randint(10 ** 11, 10 ** 12 - 1))
    sender = company(rng) if rng.random() < 0.6 else person(rng)
    receiver = person(rng)
    city, district = rng.choice(CITIES)
    ship = rand_date(rng)
    eta = ship + dt.timedelta(days=rng.randint(1, 4)) if rng.random() < 0.6 else None
    weight = Decimal(rng.randint(2, 400)) / 10
    pieces = rng.randint(1, 6)
    cod = money(rng, 50, 8000) if rng.random() < 0.35 else None
    status = rng.choice(["Teslim Edildi", "Dağıtımda", "Transfer Merkezinde", "Şubede Bekliyor"])

    d = Doc("t_cargo")
    d.add(kv("carrier", carrier))
    d.add(kv("tracking", tracking))
    d.add(kv("sender", sender))
    d.add(kv("receiver", receiver))
    d.add(kv("address", f"{rng.choice(STREETS)} No:{rng.randint(1, 140)} {district}/{city.upper()}"
                       if rng.random() < 0.5 else f"{rng.choice(STREETS)} No:{rng.randint(1, 140)}, {district}, {city}"))
    d.add(kv("ship_date", fmt_date(ship, ds)))
    if eta:
        d.add(kv("eta", fmt_date(eta, ds)))
    d.add(kv("weight", f"{fmt_num(weight, 1)} kg"))
    d.add(kv("pieces", str(pieces)))
    if cod is not None:
        d.add(kv("cod", fmt_money(cod, 0)))
    d.add(kv("status", status))
    gold = {"carrier": carrier, "tracking_no": tracking, "sender_name": sender, "receiver_name": receiver,
            "receiver_city": city, "ship_date": ship.isoformat(), "estimated_delivery": eta.isoformat() if eta else None,
            "weight_kg": str(weight), "pieces": pieces, "cod_amount": str(cod) if cod is not None else None,
            "status": status}
    return d, gold


GENERATORS = {"invoice": gen_invoice, "bank_statement": gen_bank_statement, "kap_disclosure": gen_kap,
              "cargo_notice": gen_cargo}


def ocr(text, rng, rate=0.12):
    out = []
    for ch in text:
        r = rng.random()
        if ch in OCR_CONFUSIONS and r < rate:
            out.append(OCR_CONFUSIONS[ch])
        elif ch == " " and r < 0.05:
            continue
        else:
            out.append(ch)
    return "".join(out)


VALUE_OCR = {"0": "O", "1": "l", "5": "S", "8": "B", "2": "Z"}


def ocr_value(text, rng, rate=0.1):
    """OCR that reaches values: digit -> lookalike letter (1.2S4,56). A letter inside a number, ID or date
    is always an error, so the truth stays recoverable. Names are left alone: their spelling is invented."""
    out = []
    for ch in text:
        r = rng.random()
        if ch in VALUE_OCR and r < rate:
            out.append(VALUE_OCR[ch])
        else:
            out.append(ch)
    return "".join(out)


def distractors(rng):
    """Plausible, clearly labelled lines that are not schema fields: extra dates, amounts, an IBAN, a person."""
    lines = [[("t", "Yazdırma Tarihi: "), ("v", fmt_date(rand_date(rng), 0))],
             [("t", "Referans No: "), ("v", str(rng.randint(10 ** 15, 10 ** 16 - 1)))],
             [("t", "Önceki Dönem Toplamı: "), ("v", fmt_money(money(rng, 100, 90000), 0))],
             [("t", "Müşteri Temsilcisi: "), ("v", person(rng))],
             [("t", "Eski IBAN (kullanılmamaktadır): "), ("v", ids.group4(ids.make_iban(rng, "90009")))]]
    return rng.sample(lines, 4)


def render(doc: Doc, variant: str, rng) -> str:
    blocks = list(doc.blocks)
    if variant == "distractors":
        for line in distractors(rng):
            blocks.insert(rng.randint(1, len(blocks)), (False, [line]))
    if variant == "reordered":
        slots = [i for i, (movable, _) in enumerate(blocks) if movable]
        moved = [blocks[i] for i in slots]
        rng.shuffle(moved)
        for i, b in zip(slots, moved):
            blocks[i] = b
    lines = []
    for _, block in blocks:
        for line in block:
            parts = []
            for kind, x in line:
                if kind == "label":
                    tr, en = LABELS[x]
                    text = rng.choice([en, en, f"{tr} / {en}"]) if variant == "mixed" else tr
                    parts.append(ocr(text, rng) if variant in ("ocr", "ocr_values") else text)
                elif kind == "t":
                    parts.append(ocr(x, rng) if variant in ("ocr", "ocr_values") else x)
                else:
                    parts.append(ocr_value(x, rng) if variant == "ocr_values" else x)
            lines.append("".join(parts))
    text = "\n".join(lines)
    return text.translate(ASCII_MAP) if variant == "ascii" else text


def build_dataset(per_type: int, seed: int = 2026):
    """Deterministic: same (per_type, seed) gives byte-identical output."""
    rows = []
    for doc_type in DOC_TYPES:
        for n in range(per_type):
            base_rng = random.Random(f"{seed}:{doc_type}:{n}")
            doc, gold = GENERATORS[doc_type](base_rng)
            for variant in VARIANTS:
                vrng = random.Random(f"{seed}:{doc_type}:{n}:{variant}")
                rows.append({"id": f"{doc_type}-{n:02d}-{variant}", "doc_type": doc_type, "variant": variant,
                             "synthetic": True, "text": render(doc, variant, vrng), "gold": gold})
    return rows
