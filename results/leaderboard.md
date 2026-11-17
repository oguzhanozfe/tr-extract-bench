### Shared sample: every lane on the same 28 tasks

Base document 00 of each type in every variant. Every lane ran this sample first, so it is the like-for-like comparison when a lane could not finish the full set.

| Lane | Tasks scored | F1 | Precision | Recall | JSON valid % | Hallucinated % | Median latency s | Unscored API errors |
|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 28/28 | 99.6 | 99.6 | 99.6 | 100.0 | 0.0 | 1.9 | 0 |
| ollama-qwen3.5-9b | 28/28 | 99.6 | 99.6 | 99.6 | 100.0 | 0.0 | 17.6 | 0 |
| gemini-3.5-flash-lite | 28/28 | 99.2 | 99.2 | 99.2 | 100.0 | 0.0 | 1.7 | 0 |
| gemma-4-31b-it | 21/28 (partial) | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 56.9 | 2 |
| ollama-qwen3.5-4b | 28/28 | 91.5 | 91.8 | 91.1 | 100.0 | 0.0 | 2.9 | 0 |

### All tasks a lane completed

| Lane | Tasks scored | F1 | Precision | Recall | JSON valid % | Hallucinated % | Median latency s | Unscored API errors |
|---|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 224/224 | 99.3 | 99.3 | 99.3 | 100.0 | 0.0 | 1.9 | 0 |
| gemini-3.5-flash-lite | 224/224 | 99.0 | 99.1 | 98.9 | 100.0 | 0.0 | 1.3 | 0 |
| ollama-qwen3.5-9b | 224/224 | 98.4 | 99.0 | 97.9 | 99.6 | 0.0 | 8.3 | 0 |
| ollama-qwen3.5-4b | 224/224 | 95.1 | 95.8 | 94.5 | 99.1 | 0.0 | 3.0 | 0 |
| gemma-4-31b-it | 21/224 (partial) | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 56.9 | 2 |

### F1 by document type

| Lane | invoice | bank_statement | kap_disclosure | cargo_notice |
|---|---|---|---|---|
| gemini-3.1-flash-lite | 98.9 | 99.2 | 100.0 | 99.6 |
| gemini-3.5-flash-lite | 98.3 | 99.2 | 99.7 | 99.3 |
| ollama-qwen3.5-9b | 98.1 | 98.2 | 97.9 | 99.4 |
| ollama-qwen3.5-4b | 98.3 | 85.1 | 97.4 | 99.4 |
| gemma-4-31b-it | 100.0 | 100.0 | 100.0 | 100.0 |

### F1 by noise variant

| Lane | clean | ocr | ascii | mixed | reordered | ocr_values | distractors |
|---|---|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 95.3 | 100.0 |
| gemini-3.5-flash-lite | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 93.2 | 99.7 |
| ollama-qwen3.5-9b | 99.8 | 99.8 | 99.8 | 99.8 | 99.5 | 90.1 | 99.8 |
| ollama-qwen3.5-4b | 98.0 | 95.5 | 95.4 | 97.0 | 95.1 | 87.9 | 96.8 |
| gemma-4-31b-it | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | – |

Settings: `gemini-3.1-flash-lite` temperature=0, thinkingLevel=low; `gemini-3.5-flash-lite` temperature=0, thinkingLevel=low; `ollama-qwen3.5-9b` temperature=0, think=false, digest=56671c2ab938; `ollama-qwen3.5-4b` temperature=0, think=false, digest=2a654d98e6fb; `gemma-4-31b-it` temperature=0, thought parts dropped
