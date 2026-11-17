### Shared sample: every lane on the same 20 tasks

Base document 00 of each type in all five variants. Cloud free tiers allow about 20 requests per model per day, so this is the like-for-like comparison.

| Lane | Tasks scored | F1 | Precision | Recall | JSON valid % | Hallucinated % | Median latency s | Unscored API errors |
|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 20/20 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 1.9 | 0 |
| gemini-3.5-flash-lite | 20/20 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 1.7 | 0 |
| ollama-qwen3.5-9b | 20/20 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 21.3 | 0 |
| gemma-4-31b-it | 0/20 (partial) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3 |

### All tasks a lane completed

| Lane | Tasks scored | F1 | Precision | Recall | JSON valid % | Hallucinated % | Median latency s | Unscored API errors |
|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 20/160 (partial) | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 1.9 | 0 |
| ollama-qwen3.5-9b | 160/160 | 99.8 | 99.9 | 99.6 | 100.0 | 0.0 | 13.1 | 0 |
| gemini-3.5-flash-lite | 35/160 (partial) | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 1.6 | 1 |
| gemma-4-31b-it | 0/160 (partial) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3 |

### F1 by document type

| Lane | invoice | bank_statement | kap_disclosure | cargo_notice |
|---|---|---|---|---|
| gemini-3.1-flash-lite | 100.0 | 100.0 | 100.0 | 100.0 |
| ollama-qwen3.5-9b | 100.0 | 99.7 | 98.9 | 100.0 |
| gemini-3.5-flash-lite | 100.0 | 100.0 | 100.0 | 100.0 |
| gemma-4-31b-it | – | – | – | – |

### F1 by noise variant

| Lane | clean | ocr | ascii | mixed | reordered |
|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| ollama-qwen3.5-9b | 99.8 | 99.8 | 99.8 | 99.8 | 99.5 |
| gemini-3.5-flash-lite | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| gemma-4-31b-it | – | – | – | – | – |

Settings: `gemini-3.1-flash-lite` temperature=0, thinkingLevel=low; `ollama-qwen3.5-9b` temperature=0, think=false, digest=56671c2ab938; `gemini-3.5-flash-lite` temperature=0, thinkingLevel=low; `gemma-4-31b-it` temperature=0, thought parts dropped
