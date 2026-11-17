# tr-extract-bench

A small, reproducible benchmark for pulling structured JSON out of Turkish business
documents with LLMs: e-fatura style invoices, bank statement excerpts, KAP-style
company disclosures and cargo notices. Every document is synthetic and comes with exact
ground truth, so scoring is mechanical rather than judged by another model.

## Why it matters

Most extraction benchmarks are English. Turkish documents bring their own failure
modes: `1.234,56 TL` number formats, `17 Kasım 2026` dates, VKN/TCKN/IBAN identifiers,
dotted and dotless i, and scans or exports where `ş` has become `s`. Before choosing a
model for invoice or statement intake you want to know how it handles those, how often
it returns broken JSON, and whether it invents values for fields that are not there.

## What is in the box

- **Dataset** (`data/docs.jsonl`): 32 base documents (8 per type), each rendered in 7
  variants, so 224 extraction tasks. Built by a seeded generator; CI checks the committed
  file regenerates byte for byte.
- **Noise variants**, applied to the rendered text only (ground truth never changes).
  Baseline tier (160 tasks):
  - `clean`: Turkish labels, canonical layout
  - `ocr`: character confusions in labels and prose (`ş→s`, `l→1`, `m→rn`, `S→5`, dropped
    spaces). Values are left intact so the truth stays recoverable.
  - `ascii`: Turkish letters stripped everywhere (`ı→i`, `ş→s`, `ğ→g`, ...)
  - `mixed`: labels in English or `TR / EN`
  - `reordered`: field blocks shuffled

  Hard tier (64 tasks), added after every lane scored about 100% on the baseline tier:
  - `ocr_values`: label and prose OCR as above, plus OCR inside values: digits become
    lookalike letters (`0→O`, `1→l`, `5→S`, `8→B`, `2→Z`) in amounts, dates, IDs and IBANs.
    A letter inside a purely numeric field is always an error, so the truth stays
    recoverable. `invoice_no` is alphanumeric (3 letters, year, 9 digits), so undoing a swap
    there requires knowing the e-fatura number format. Names are not touched, because their
    invented spelling could not be recovered.
  - `distractors`: four extra labelled lines that are not schema fields, picked from: print date,
    reference number, previous-period total, customer representative, a closed account's IBAN
- **Identifiers** are checksum-valid but fictional: VKN and TCKN by the official check-digit
  rules, TR IBANs by ISO 13616 mod-97 with bank codes `9000x`, chosen to look unlike real bank codes (not checked against the full EFT
  list). The
  algorithms are tested against published reference values and were cross-checked against
  `python-stdnum` during development. Every document carries a visible
  `SENTETİK ÖRNEK BELGE / SYNTHETIC TEST DOCUMENT` line and `"synthetic": true`.
- **Optional fields** (due date, payment IBAN, overdraft limit, counterparty, ETA,
  cash-on-delivery...) are absent from some documents, so a model that fills them in is
  caught.

## Scoring

Per field, against the clean canonical value. A missing key counts as `null`.

| Field type | Match rule |
|---|---|
| amount | parsed with `Decimal` from `1.234,56 TL`, `1234.56`, `TL 1.234,56`...; equal to the cent |
| number / int | same parser (also strips `%`, `kg`) |
| date | ISO, `dd.mm.yyyy`, `dd/mm/yyyy`, `17 Kasım 2026` (ASCII and English month names too) |
| tax office | as string, ignoring a trailing `V.D.` / `Vergi Dairesi` |
| id | uppercase, spaces, dots and dashes removed |
| string / enum | Turkish-aware fold (`İ I ı → i`, `ş→s` ...), lowercase, punctuation dropped. Matching therefore ignores diacritics: the `ascii` variant makes them unrecoverable. |

- **TP** non-null prediction that matches; **FP** non-null prediction that is wrong or where
  the truth is null; **FN** truth is non-null and the prediction is null or wrong.
  Precision, recall and F1 are micro-averaged over all fields.
- **JSON valid %**: output parses as a JSON object, after removing `<think>`/`<thought>`
  blocks and one surrounding `` ``` `` fence, and nothing else. Invalid output scores every true field as a false negative.
- **Hallucinated %**: share of emitted non-null values that are either for a field whose
  truth is null or for a key outside the schema.
- No constrained decoding or JSON mode is used, so JSON validity is a real measurement.
- Line items and transaction rows are shown in the documents but not extracted; only
  totals are scored.

## Results

Measured on 2026-11-17. Every number below is generated from `results/raw/*.jsonl` by
`python -m trbench score`; CI fails if this table drifts from the recorded outputs.

What the recorded runs show:

- **The baseline tier is at ceiling.** On `clean`, `ocr` (labels only), `ascii`, `mixed`
  and `reordered`, both Gemini flash-lite lanes score 100.0 F1 and `qwen3.5:9b` 99.5 to
  99.8 (`qwen3.5:4b`: 95.1 to 98.0). For label-value documents, label noise, stripped diacritics and shuffled layout
  barely matter.
- **OCR inside values is what separates models.** On `ocr_values` the full-set lanes score
  95.3 (`gemini-3.1-flash-lite`), 93.2 (`gemini-3.5-flash-lite`), 90.1 (`qwen3.5:9b`) and
  87.9 (`qwen3.5:4b`). Most misses copy the lookalike letter into an ID (`JFCZ026...`,
  `TR34...S855086`) instead of correcting it.
- **Turkish number format trips the small local model.** `qwen3.5:4b` reads balances like
  `89.625,39` as `89.62539`, so its bank-statement F1 is 85.1 while every other lane scores
  98 or more.
- **Almost no invented values.** `qwen3.5:4b` filled one absent field across 224 tasks;
  no other lane filled any. JSON validity was
  99.1% or higher without any JSON mode, and the distractor lines barely moved any lane.
- **Latency** (median per document): flash-lite lanes 1.3 to 1.9 s over the network;
  `qwen3.5:9b` 8.3 s and `qwen3.5:4b` 3.0 s on a shared Mac.

Lanes and why some are partial:

- Both Ollama lanes (`qwen3.5:9b`, `qwen3.5:4b`) ran all 224 tasks on a local Mac. The 9b
  lane shared the Ollama server with other jobs; the 4b lane ran in a quiet window, so their
  latencies are not like for like.
- Cloud lanes use the Gemini API free tier. `gemini-3.5-flash` hit the free tier's
  per-day quota (20 requests) after 22 recorded tasks, so it was dropped. Both flash-lite lanes completed all 224
  tasks. `gemma-4-31b-it` answered slowly (about a minute per document, with long
  reasoning) and often returned HTTP 503, so it ran only on the shared sample and finished 21
  of its 28 tasks. Its 100.0 covers mostly baseline-tier tasks and is not comparable with
  the full-set lanes. A lane marked partial ran out of quota or
  time; its scores cover only the tasks it completed.
- DeepSeek has an adapter, but the account had a zero balance (HTTP 402), so it was not run.
- Requests that failed at the transport or API level (timeouts, HTTP 503) are retried and
  listed as unscored API errors. They are not counted as model mistakes.

<!-- LEADERBOARD:START -->
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
| gemma-4-31b-it | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | – | – |

`–`: fewer than 4 scored tasks in that bucket.

Settings: `gemini-3.1-flash-lite` temperature=0, thinkingLevel=low; `gemini-3.5-flash-lite` temperature=0, thinkingLevel=low; `ollama-qwen3.5-9b` temperature=0, think=false, digest=56671c2ab938; `ollama-qwen3.5-4b` temperature=0, think=false, digest=2a654d98e6fb; `gemma-4-31b-it` temperature=0, thought parts dropped
<!-- LEADERBOARD:END -->

## How to run

Python 3.10+, standard library only.

```bash
python -m unittest discover -s tests       # offline tests
python -m trbench gen --check              # dataset regenerates byte for byte
python -m trbench score                    # rescore recorded outputs into results/ and this README
```

To run models yourself:

```bash
python -m trbench lanes                    # what is available on this machine
python -m trbench run                      # all lanes; resumable, one JSONL row per document
python -m trbench run --lane ollama-qwen3.5-9b --limit 10
python -m trbench run --lane gemini-3.5-flash-lite --sample 1   # only the shared sample
```

Lanes are discovered automatically:

- every chat model in a local Ollama (`OLLAMA_URL`, default `http://127.0.0.1:11434`);
  embedding models are skipped because they cannot chat
- Gemini API models if `GEMINI_API_KEY` is set (`TRB_GEMINI_MODELS`, comma-separated, default
  `gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b-it`)
- DeepSeek if `DEEPSEEK_API_KEY` is set (`TRB_DEEPSEEK_MODEL`, default `deepseek-flash`)
- OpenAI if `OPENAI_API_KEY` is set, Anthropic if `ANTHROPIC_API_KEY` is set

Lanes run at temperature 0. Thinking is off for Ollama and set to `low` for Gemini models;
`gemma-4-31b-it` accepts no thinking setting and reasons by default (its thought parts are
dropped before scoring). The OpenAI lane uses default settings. The exact settings (and the Ollama model digest) are stored in every result row.

## Known limits

- **Synthetic, template-generated text.** Eight base documents per type is small, and
  real e-fatura PDFs, bank exports and KAP pages are messier. Treat the numbers as a
  comparison between models on the same task, not as accuracy you will see in production.
- **Text only.** The `ocr` variant simulates OCR errors in text; there is no image or PDF
  input.
- **Latency is indicative.** Local runs shared one Mac and its Ollama server with other
  workloads; cloud latency includes the network.
- **One run per model** at temperature 0, no repeat runs or confidence intervals. The
  shared sample is 28 tasks, so differences of a few points between lanes are noise.
- **Easy baseline.** The baseline tier uses clean label-value layouts and is at ceiling for
  every lane. Only `ocr_values` separates models so far.
- **Judgement calls in the gold.** For a new-contract KAP disclosure the signing date is
  scored as `effective_date`; a model that returns null there loses recall.
- Diacritic-insensitive string matching means a model that strips `ş` from a correct name
  is not penalised.
- Company, bank and carrier names are composed from invented words; any resemblance to a
  real entity is coincidental. Tax office and city names are real place names.

## Türkçe özet

`tr-extract-bench`, LLM'lerin Türkçe ticari belgelerden (e-fatura, hesap ekstresi, KAP
özel durum açıklaması, kargo bildirimi) yapılandırılmış JSON çıkarma başarısını ölçen küçük
ve tekrarlanabilir bir benchmark'tır. Tüm belgeler sentetiktir ve kesin doğru cevapları
(ground truth) vardır; VKN, TCKN ve IBAN değerleri kontrol hanesi geçerli ama hayalidir.

Her belge yedi varyantta üretilir: temiz, OCR hatalı, Türkçe karakterleri silinmiş,
TR/EN karışık etiketli, alanları karıştırılmış; ayrıca zor katmanda değerlerin içine de OCR
hatası girmiş (`5→S`, `0→O`) ve dikkat dağıtıcı satırlar eklenmiş varyantlar. Puanlama alan bazındadır: tutarlar
(`1.234,56 TL`), tarihler (`17 Kasım 2026`) ve kimlik numaraları türüne göre normalize
edilir; ayrıca geçerli JSON oranı ve belgede olmayan alanlar için uydurulan değer oranı
(halüsinasyon) raporlanır. Sonuç tablosu yukarıdadır ve kayıtlı model çıktılarından
yeniden üretilir.

Çalıştırmak için: `python -m unittest discover -s tests` ve `python -m trbench score`.
Kendi modellerinizi denemek için `python -m trbench run`.

## License

MIT
