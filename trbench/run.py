"""Model lanes and the resumable benchmark runner.

Each lane appends one JSON row per document to results/raw/<lane>.jsonl, so an
interrupted run resumes where it stopped. Rows hold only the model output,
latency and settings: no URLs, headers, hostnames or keys.
"""
import json
import os
import time
import urllib.error
import urllib.request

from .docs import SCHEMAS

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
GEMINI_MODELS = os.environ.get("TRB_GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b-it").split(",")
DEEPSEEK_MODEL = os.environ.get("TRB_DEEPSEEK_MODEL", "deepseek-flash")
LMSTUDIO_URL = os.environ.get("LMSTUDIO_URL")  # e.g. http://<gpu-box>:1234/v1 ; opt-in, no default
LMSTUDIO_MODELS = [m for m in os.environ.get("TRB_LMSTUDIO_MODELS", "").split(",") if m]  # empty = all chat models
GROQ_MODELS = os.environ.get("TRB_GROQ_MODELS", "qwen/qwen3.8-27b,openai/gpt-oss-120b").split(",")
OPENAI_MODEL = os.environ.get("TRB_OPENAI_MODEL", "gpt-5-mini")
ANTHROPIC_MODEL = os.environ.get("TRB_ANTHROPIC_MODEL", "claude-haiku-5-5")
SYSTEM = "You extract structured data from Turkish business documents. Reply with one JSON object and nothing else."


def prompt(doc_type: str, text: str) -> str:
    lines = []
    for name, ftype, desc in SCHEMAS[doc_type]:
        if ftype == "tax_office":
            ftype = "str"
        if ftype.startswith("enum:"):
            desc += "; one of: " + ", ".join(ftype[5:].split("|"))
            ftype = "string"
        lines.append(f'- "{name}" ({ftype}): {desc}')
    return ("Extract these fields from the document below.\n" + "\n".join(lines) +
            "\n\nRules: output only a JSON object with exactly these keys. Use null when a field is not in the "
            "document; do not guess. Dates as YYYY-MM-DD. Amounts and numbers as JSON numbers with a dot "
            "decimal separator (1234.56), no currency. IDs and IBANs without spaces.\n\nDOCUMENT:\n" + text)


def _post(url, body, headers, timeout=300):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "tr-extract-bench/0.1", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ollama_models():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=5) as r:
            models = {m["name"]: m.get("digest", "")[:12] for m in json.load(r)["models"]}
    except OSError:
        return {}
    return {n: d for n, d in sorted(models.items()) if "embed" not in n}  # embedding models cannot chat


LMSTUDIO_NOTES = {"qwen3.8-27b-uncensored-hauhaucs-aggressive-mtp": "community fine-tune of Qwen3.8-27B, "}


def lmstudio_models():
    if not LMSTUDIO_URL:
        return []
    try:
        with urllib.request.urlopen(LMSTUDIO_URL + "/models", timeout=5) as r:
            ids = [m["id"] for m in json.load(r)["data"]]
    except OSError:
        return []
    return sorted(i for i in ids if "embed" not in i and (not LMSTUDIO_MODELS or i in LMSTUDIO_MODELS))


def call_lmstudio(model, p):
    d = _post(LMSTUDIO_URL + "/chat/completions", {"model": model, "temperature": 0,
                                                   "messages": [{"role": "system", "content": SYSTEM},
                                                                {"role": "user", "content": p}]}, {}, timeout=600)
    return d["choices"][0]["message"]["content"]


def call_ollama(model, p):
    d = _post(OLLAMA_URL + "/api/chat", {"model": model, "stream": False, "think": False,
                                         "options": {"temperature": 0, "num_ctx": 8192},
                                         "messages": [{"role": "system", "content": SYSTEM},
                                                      {"role": "user", "content": p}]}, {})
    return d["message"]["content"]


def call_gemini(model, p):
    d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
              {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": [{"parts": [{"text": p}]}],
               "generationConfig": {"temperature": 0, **({"thinkingConfig": {"thinkingLevel": "low"}}
                                                         if model.startswith("gemini") else {})}},
              {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    return "".join(part.get("text", "") for part in d["candidates"][0]["content"]["parts"]
                   if not part.get("thought"))


def _openai_compat(base, key_env, model, p, extra):
    d = _post(base + "/chat/completions", {"model": model, "temperature": 0, **extra,
                                           "messages": [{"role": "system", "content": SYSTEM},
                                                        {"role": "user", "content": p}]},
              {"Authorization": "Bearer " + os.environ[key_env]})
    return d["choices"][0]["message"]["content"]


def call_anthropic(model, p):
    d = _post("https://api.anthropic.com/v1/messages",
              {"model": model, "max_tokens": 2048, "temperature": 0, "system": SYSTEM,
               "messages": [{"role": "user", "content": p}]},
              {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in d["content"])


def lanes():
    """lane name -> (model, settings, callable(prompt) -> text, min seconds between calls)."""
    out = {}
    for m, digest in ollama_models().items():
        out["ollama-" + m.replace(":", "-")] = (m, f"temperature=0, think=false, digest={digest}", lambda p, m=m: call_ollama(m, p), 0)
    for gm in GEMINI_MODELS if os.environ.get("GEMINI_API_KEY") else []:
        settings = "temperature=0" + (", thinkingLevel=low" if gm.startswith("gemini") else ", thought parts dropped")
        out[gm] = (gm, settings, lambda p, gm=gm: call_gemini(gm, p), 7)
    if os.environ.get("DEEPSEEK_API_KEY"):
        out[DEEPSEEK_MODEL] = (DEEPSEEK_MODEL, "temperature=0, reasoning_effort=low",
                                             lambda p: _openai_compat("https://api.deepseek.com", "DEEPSEEK_API_KEY",
                                                                      DEEPSEEK_MODEL, p, {"reasoning_effort": "low"}), 0)
    for m in lmstudio_models():  # sequential requests only: one shared GPU
        note = LMSTUDIO_NOTES.get(m, "")
        out["lmstudio-" + m.replace("/", "-")] = (m, f"temperature=0, {note}local RTX 3090 via LM Studio",
                                                  lambda p, m=m: call_lmstudio(m, p), 0)
    for gm in GROQ_MODELS if os.environ.get("GROQ_API_KEY") else []:
        effort = "low" if gm.startswith("openai/gpt-oss") else "none"  # reasoning off where the model allows it
        out["groq-" + gm.replace("/", "-")] = (
            gm, f"temperature=0, reasoning_effort={effort}",
            lambda p, gm=gm, effort=effort: _openai_compat("https://api.groq.com/openai/v1", "GROQ_API_KEY", gm, p,
                                                           {"reasoning_effort": effort}), 12)  # free tier: 8k tokens/min
    if os.environ.get("OPENAI_API_KEY"):
        out["openai-" + OPENAI_MODEL] = (OPENAI_MODEL, "default settings",
                                         lambda p: _openai_compat("https://api.openai.com/v1", "OPENAI_API_KEY",
                                                                  OPENAI_MODEL, p, {}), 0)
    if os.environ.get("ANTHROPIC_API_KEY"):
        out["anthropic-" + ANTHROPIC_MODEL] = (ANTHROPIC_MODEL, "temperature=0",
                                               lambda p: call_anthropic(ANTHROPIC_MODEL, p), 0)
    return out


def run_lane(lane, spec, rows, out_path, limit=None):
    model, settings, call, gap = spec
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            done = {r["id"] for r in map(json.loads, filter(str.strip, f)) if not r["error"]}  # retry errors
    todo = [r for r in rows if r["id"] not in done][:limit]
    print(f"{lane}: {len(done)} done, {len(todo)} to run", flush=True)
    for row in todo:
        for attempt in range(5):
            t0 = time.monotonic()
            try:
                text, err = call(prompt(row["doc_type"], row["text"])), None
            except urllib.error.HTTPError as e:
                text, err = None, f"HTTP {e.code}"
                if e.code in (429, 500, 502, 503) and attempt < 4:
                    time.sleep(30 * (attempt + 1))
                    continue
            except OSError as e:  # timeouts / connection resets on a shared Ollama: retry
                text, err = None, type(e).__name__
                if attempt < 4:
                    time.sleep(15 * (attempt + 1))
                    continue
            except (KeyError, IndexError, ValueError) as e:
                text, err = None, type(e).__name__
            break
        if err == "HTTP 429":  # quota still exhausted after backoff (free tiers cap requests per day)
            print(f"{lane}: stopping, quota exhausted", flush=True)
            return
        latency = round(time.monotonic() - t0, 2)
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": row["id"], "lane": lane, "model": model, "settings": settings,
                                "latency_s": latency, "error": err, "output": text}, ensure_ascii=False) + "\n")
        print(f"  {row['id']} {latency}s {err or ''}", flush=True)
        if gap:
            time.sleep(gap)
