"""Leaderboard tables from recorded raw outputs."""
import glob
import json
import os
import statistics

from .docs import DOC_TYPES, VARIANTS
from .score import aggregate, score_item

START, END = "<!-- LEADERBOARD:START -->", "<!-- LEADERBOARD:END -->"


def _pct(x):
    return f"{100 * x:.1f}"


def build(dataset, raw_dir):
    by_id = {r["id"]: r for r in dataset}
    lanes = {}
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        if not rows:
            continue
        rows = list({r["id"]: r for r in rows}.values())  # a retried task keeps its last attempt
        items = []
        for row in rows:
            doc = by_id[row["id"]]
            s = score_item(doc["doc_type"], doc["gold"], row["output"] or "")
            s.update(doc_type=doc["doc_type"], variant=doc["variant"], latency=row["latency_s"],
                     sample=int(row["id"].split("-")[-2]) == 0,
                     error=row["error"])
            items.append(s)
        lanes[rows[0]["lane"]] = {"model": rows[0]["model"], "settings": rows[0]["settings"], "items": items}
    return lanes, len(dataset), sum(1 for r in dataset if r["id"].split("-")[-2] == "00")


def _table(lanes, order, total, pick):
    out = ["| Lane | Tasks scored | F1 | Precision | Recall | JSON valid % | Hallucinated % | Median latency s | Unscored API errors |",
           "|---|---|---|---|---|---|---|---|---|"]
    for k in order:
        everything = [i for i in lanes[k]["items"] if pick(i)]
        it = [i for i in everything if not i["error"]]  # transport/API errors are not model answers
        if not everything:
            continue
        a = aggregate(it)
        ok = [i["latency"] for i in it]
        n = f"{a['n']}/{total}" + ("" if a["n"] == total else " (partial)")
        out.append(f"| {k} | {n} | {_pct(a['f1'])} | {_pct(a['precision'])} | {_pct(a['recall'])} | "
                   f"{_pct(a['json_valid'])} | {_pct(a['halluc_rate'])} | "
                   f"{statistics.median(ok) if ok else 0:.1f} | {len(everything) - len(it)} |")
    return out


def markdown(lanes, total, sample_total):
    order = sorted(lanes, key=lambda k: -aggregate(lanes[k]["items"])["f1"])
    out = [f"### Shared sample: every lane on the same {sample_total} tasks", "",
           "Base document 00 of each type in every variant. Every lane ran this sample first, so it is the "
           "like-for-like comparison when a lane could not finish the full set.", ""]
    out += _table(lanes, sorted(lanes, key=lambda k: -aggregate([i for i in lanes[k]["items"] if i["sample"]])["f1"]),
                  sample_total, lambda i: i["sample"])
    out += ["", "### All tasks a lane completed", ""]
    out += _table(lanes, order, total, lambda i: True)
    for title, key, values in (("F1 by document type", "doc_type", DOC_TYPES),
                               ("F1 by noise variant", "variant", VARIANTS)):
        out += ["", f"### {title}", "", "| Lane | " + " | ".join(values) + " |",
                "|---|" + "---|" * len(values)]
        for k in order:
            groups = [[i for i in lanes[k]["items"] if i[key] == v and not i["error"]] for v in values]
            cells = [_pct(aggregate(g)["f1"]) if len(g) >= 4 else "–" for g in groups]
            out.append(f"| {k} | " + " | ".join(cells) + " |")
    out += ["", "`–`: fewer than 4 scored tasks in that bucket.", "", "Settings: " + "; ".join(f"`{k}` {lanes[k]['settings']}" for k in order)]
    return "\n".join(out) + "\n"


def summary_json(lanes):
    res = {}
    for k, v in sorted(lanes.items()):
        it = [i for i in v["items"] if not i["error"]]
        res[k] = {"model": v["model"], "settings": v["settings"], "overall": aggregate(it),
                  "by_doc_type": {d: aggregate([i for i in it if i["doc_type"] == d]) for d in DOC_TYPES},
                  "by_variant": {x: aggregate([i for i in it if i["variant"] == x]) for x in VARIANTS}}
    return json.dumps(res, indent=2, sort_keys=True) + "\n"


def write_reports(dataset, raw_dir, root, check=False):
    """Write results/leaderboard.md, results/scores.json and the README block. Return stale paths."""
    lanes, total, sample_total = build(dataset, raw_dir)
    md = markdown(lanes, total, sample_total)
    targets = {os.path.join(root, "results", "leaderboard.md"): md,
               os.path.join(root, "results", "scores.json"): summary_json(lanes)}
    readme = os.path.join(root, "README.md")
    if os.path.exists(readme):
        text = open(readme, encoding="utf-8").read()
        if START in text and END in text:
            head, rest = text.split(START, 1)
            targets[readme] = head + START + "\n" + md + END + rest.split(END, 1)[1]
    stale = []
    for path, content in targets.items():
        current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if current != content:
            stale.append(os.path.relpath(path, root))
            if not check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
    return stale
