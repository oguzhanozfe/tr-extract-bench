"""python -m trbench gen|run|score [--check]"""
import argparse
import json
import os
import sys

from .docs import build_dataset
from .report import write_reports
from .run import lanes, run_lane

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "docs.jsonl")
RAW = os.path.join(ROOT, "results", "raw")
PER_TYPE = 8


def dump(rows):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def base_index(doc_id):
    return int(doc_id.split("-")[-2])


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="trbench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="write data/docs.jsonl")
    g.add_argument("--check", action="store_true", help="fail if the committed dataset differs")
    sub.add_parser("lanes", help="list lanes available on this machine")
    d = sub.add_parser("demo", help="extract and score a few documents; works with no key")
    d.add_argument("--mode", choices=["auto", "live", "replay"], default="auto")
    r = sub.add_parser("run", help="run lanes (default: all available)")
    r.add_argument("--lane", action="append")
    r.add_argument("--limit", type=int)
    r.add_argument("--sample", type=int, help="only base documents with index < N (e.g. 1 = the shared sample)")
    s = sub.add_parser("score", help="score results/raw/*.jsonl into results/ and README")
    s.add_argument("--check", action="store_true", help="fail if committed reports are stale")
    a = ap.parse_args(argv)

    if a.cmd == "gen":
        text = dump(build_dataset(PER_TYPE))
        if a.check:
            ok = os.path.exists(DATA) and open(DATA, encoding="utf-8").read() == text
            print("dataset reproducible" if ok else "dataset differs from generator")
            return 0 if ok else 1
        os.makedirs(os.path.dirname(DATA), exist_ok=True)
        with open(DATA, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {text.count(chr(10))} rows")
    elif a.cmd == "demo":
        from .demo import run_demo
        return run_demo(a.mode, load(DATA), RAW)
    elif a.cmd == "lanes":
        for name, (model, settings, _, _) in lanes().items():
            print(f"{name}\t{settings}")
    elif a.cmd == "run":
        available, rows = lanes(), load(DATA)
        if a.sample is not None:
            rows = [x for x in rows if base_index(x["id"]) < a.sample]
        os.makedirs(RAW, exist_ok=True)
        for name in a.lane or list(available):
            if name not in available:
                sys.exit(f"lane not available: {name}")
            run_lane(name, available[name], rows, os.path.join(RAW, name + ".jsonl"), a.limit)
    else:
        stale = write_reports(load(DATA), RAW, ROOT, check=a.check)
        if a.check:
            print("reports stale: " + ", ".join(stale) if stale else "reports up to date")
            return 1 if stale else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
