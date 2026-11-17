"""Static GitHub Pages report (docs/index.html): leaderboard plus worked examples from recorded outputs."""
import html
import json
import os
import re

from .score import field_checks, parse_output

# (lane, task id, why it is shown). All outputs come from results/raw/.
EXAMPLES = [
    ("ollama-qwen3.5-4b", "bank_statement-00-clean", "Reads the Turkish thousands separator as a decimal point."),
    ("gemini-3.1-flash-lite", "invoice-07-ocr_values", "Copies OCR letters into IDs instead of correcting them."),
    ("ollama-qwen3.5-4b", "kap_disclosure-06-distractors", "Takes an amount from a distractor line for a field the "
                                                           "disclosure does not have."),
    ("gemini-3.5-flash-lite", "cargo_notice-00-distractors", "Every field right despite four distractor lines."),
]

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6862;--line:#e3e0d8;--card:#fff;--ok:#1f7a4d;--bad:#b3261e;--warn:#9a5b00;
--accent:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--muted:#a19e96;--line:#34332f;--card:#1d1c1a;
--ok:#5cc28d;--bad:#ff8a80;--warn:#f0b35a;--accent:#7db4ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:32px 16px 64px}h1{font-size:28px;margin:0 0 4px}
h2{font-size:20px;margin:40px 0 8px}h3{font-size:16px;margin:24px 0 8px}p{margin:6px 0;color:var(--muted)}
a{color:var(--accent)}code{font:13px ui-monospace,SFMono-Regular,Menlo,monospace}
.wrap{overflow-x:auto}table{border-collapse:collapse;font-size:14px;width:100%;background:var(--card)}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{background:var(--bg)}
.ex{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:16px;margin:16px 0}
.ex h3{margin:0 0 2px}.cols{display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:12px;margin-top:10px}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
pre{margin:0;padding:10px;background:var(--bg);border:1px solid var(--line);border-radius:6px;overflow-x:auto;
font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;word-break:break-word}
.lbl{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:4px}
.checks td,.checks th{white-space:normal;text-align:left;font-size:13px}.ok{color:var(--ok)}.bad{color:var(--bad)}
.warn{color:var(--warn)}
"""


def _inline(text):
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text))


def md_to_html(md):
    out, table = [], []

    def flush():
        if table:
            head, body = table[0], [r for r in table[2:]]
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            out.append('<div class="wrap"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in cells(head))
                       + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells(r))
                                                          + "</tr>" for r in body) + "</tbody></table></div>")
            table.clear()

    for line in md.splitlines():
        if line.startswith("|"):
            table.append(line)
            continue
        flush()
        if line.startswith("### "):
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    flush()
    return "\n".join(out)


STATUS = {"ok": ("ok", "correct"), "wrong": ("bad", "wrong"), "missed": ("bad", "missed"),
          "invented": ("warn", "invented"), "extra": ("warn", "extra key"), "absent": ("ok", "correctly null")}


def _v(x):
    return "null" if x is None else html.escape(str(x))


def example_html(lane, doc, output, why):
    pred = parse_output(output or "")
    if pred is None:
        checks_html = "<p>Invalid JSON: every field counts as missed.</p>"
    else:
        rows = []
        for name, gold, got, status in field_checks(doc["doc_type"], doc["gold"], pred):
            cls, word = STATUS[status]
            rows.append(f'<tr><td><code>{html.escape(name)}</code></td><td>{_v(gold)}</td>'
                        f'<td>{_v(got)}</td><td class="{cls}">{word}</td></tr>')
        checks_html = ('<div class="wrap"><table class="checks"><thead><tr><th>field</th><th>truth</th>'
                       '<th>extracted</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
    shown = json.dumps(pred, ensure_ascii=False, indent=2) if pred is not None else (output or "")
    return (f'<section class="ex"><h3><code>{html.escape(doc["id"])}</code> · {html.escape(lane)}</h3>'
            f"<p>{html.escape(why)}</p><div class=\"cols\">"
            f'<div><div class="lbl">Document (synthetic)</div><pre>{html.escape(doc["text"])}</pre></div>'
            f'<div><div class="lbl">Extracted JSON</div><pre>{html.escape(shown)}</pre></div>'
            f'<div><div class="lbl">Scored against the truth</div>{checks_html}</div></div></section>')


def render(leaderboard_md, dataset, raw_dir):
    by_id = {r["id"]: r for r in dataset}
    examples = []
    for lane, doc_id, why in EXAMPLES:
        with open(os.path.join(raw_dir, lane + ".jsonl"), encoding="utf-8") as f:
            outputs = {r["id"]: r["output"] for r in map(json.loads, filter(str.strip, f))}
        examples.append(example_html(lane, by_id[doc_id], outputs[doc_id], why))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>tr-extract-bench</title><style>{CSS}</style></head><body><main>
<h1>tr-extract-bench</h1>
<p>How well LLMs pull structured JSON out of Turkish business documents: e-fatura invoices, bank statements,
KAP disclosures, cargo notices. All documents are synthetic with exact ground truth; every number here is
rebuilt from recorded model outputs. <a href="https://github.com/oguzhanozfe/tr-extract-bench">Source, method
and limits on GitHub</a>.</p>
<h2>Leaderboard</h2>
{md_to_html(leaderboard_md)}
<h2>Worked examples</h2>
<p>Recorded outputs, scored field by field. Matching rules: amounts to the cent, dates in any common
Turkish format, names ignoring diacritics.</p>
{"".join(examples)}
</main></body></html>
"""
