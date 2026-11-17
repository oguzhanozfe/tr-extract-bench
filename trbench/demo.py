"""`python -m trbench demo`: generate a few documents, extract, score. No key needed.

Model resolution: a cloud key in the environment -> that provider; else a local Ollama
chat model; else replay of the outputs recorded in results/raw/.
"""
import json
import os
import time

from .docs import build_dataset
from .report import build, markdown
from .run import lanes, prompt
from .score import aggregate, field_checks, parse_output, score_item

DEMO_IDS = ["invoice-00-ocr_values", "bank_statement-00-clean", "kap_disclosure-00-mixed",
            "cargo_notice-00-distractors"]
CLOUD_PREFERENCE = ["gemini-3.5-flash-lite", "openai-", "anthropic-"]  # DeepSeek stays out of the demo
LOCAL_PREFERENCE = ["ollama-qwen3.5-9b", "ollama-"]
REPLAY_LANE = "ollama-qwen3.5-4b"  # recorded lane with visible mistakes, so the scoring has something to show
RECORDED_ON = "2026-11-17"


def resolve(mode, raw_dir):
    """Return (label, function id -> output text)."""
    available = lanes() if mode != "replay" else {}
    for prefs, kind in ((CLOUD_PREFERENCE, "cloud"), (LOCAL_PREFERENCE, "local")):
        for pref in prefs:
            name = next((n for n in available if n.startswith(pref)), None)
            if name:
                call = available[name][2]
                return f"mode: {kind} ({name})", lambda row: call(prompt(row["doc_type"], row["text"]))
    if mode == "live":
        raise SystemExit("no cloud key and no local Ollama model found; run with --mode replay")
    with open(os.path.join(raw_dir, REPLAY_LANE + ".jsonl"), encoding="utf-8") as f:
        recorded = {r["id"]: r["output"] for r in map(json.loads, filter(str.strip, f))}
    return f"mode: replay (recorded {REPLAY_LANE}, {RECORDED_ON})", lambda row: recorded[row["id"]]


def run_demo(mode, dataset, raw_dir):
    label, extract = resolve(mode, raw_dir)
    print(label)
    rows = [r for r in build_dataset(1) if r["id"] in DEMO_IDS]  # generated fresh from the seeded generator
    items = []
    for row in rows:
        t0 = time.monotonic()
        output = extract(row) or ""
        took = time.monotonic() - t0
        s = score_item(row["doc_type"], row["gold"], output)
        items.append(s)
        print(f"\n=== {row['id']}  ({took:.1f}s)\n{row['text']}\n--- extracted")
        pred = parse_output(output)
        if pred is None:
            print("invalid JSON:", output[:200])
            continue
        checks = field_checks(row["doc_type"], row["gold"], pred)
        ok = sum(c[3] == "ok" for c in checks)
        print(f"{ok}/{sum(c[3] in ('ok', 'wrong', 'missed') for c in checks)} fields correct")
        for name, gold, got, status in checks:
            if status not in ("ok", "absent"):
                print(f"  {status:8} {name}: expected {gold!r}, got {got!r}")
    a = aggregate(items)
    print(f"\ndemo F1 {100 * a['f1']:.1f} on {len(items)} documents, JSON valid {100 * a['json_valid']:.0f}%")
    print("\nLeaderboard rebuilt from committed outputs (results/raw/):\n")
    lanes_data, total, sample_total = build(dataset, raw_dir)
    md = markdown(lanes_data, total, sample_total)
    print(md.split("### All tasks a lane completed", 1)[1].split("###", 1)[0].strip())
    return 0
