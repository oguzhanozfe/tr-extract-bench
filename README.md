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

- **Dataset** (`data/docs.jsonl`): 32 base documents (8 per type), each rendered in 5
  variants, so 160 extraction tasks. Built by a seeded generator; CI checks the committed
  file regenerates byte for byte.
- **Noise variants**, applied to the rendered text only (ground truth never changes):
  - `clean`: Turkish labels, canonical layout
  - `ocr`: character confusions in labels and prose (`ş→s`, `l→1`, `m→rn`, `S→5`, dropped
    spaces). Values are left intact so the truth stays recoverable.
  - `ascii`: Turkish letters stripped everywhere (`ı→i`, `ş→s`, `ğ→g`, ...)
  - `mixed`: labels in English or `TR / EN`
  - `reordered`: field blocks shuffled
- **Identifiers** are checksum-valid but fictional: VKN and TCKN by the official check-digit
  rules, TR IBANs by ISO 13616 mod-97 with bank codes in the unused `9xxxx` range. The
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

<!-- LEADERBOARD:START -->
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
```

Lanes are discovered automatically:

- every chat model in a local Ollama (`OLLAMA_URL`, default `http://127.0.0.1:11434`);
  embedding models are skipped because they cannot chat
- Gemini if `GEMINI_API_KEY` is set (`TRB_GEMINI_MODEL`, default `gemini-3.5-flash`)
- DeepSeek if `DEEPSEEK_API_KEY` is set (`TRB_DEEPSEEK_MODEL`, default `deepseek-flash`)
- OpenAI if `OPENAI_API_KEY` is set, Anthropic if `ANTHROPIC_API_KEY` is set

All lanes run at temperature 0 with thinking off or at its lowest setting; the exact
settings (and the Ollama model digest) are stored in every result row.

## Known limits

- **Synthetic, template-generated text.** Eight base documents per type is small, and
  real e-fatura PDFs, bank exports and KAP pages are messier. Treat the numbers as a
  comparison between models on the same task, not as accuracy you will see in production.
- **Text only.** The `ocr` variant simulates OCR errors in text; there is no image or PDF
  input.
- **Latency is indicative.** Local runs shared one Mac and its Ollama server with other
  workloads; cloud latency includes the network.
- **One run per model** at temperature 0, no repeat runs or confidence intervals.
- Diacritic-insensitive string matching means a model that strips `ş` from a correct name
  is not penalised.
- Company, bank and carrier names are composed from invented words; any resemblance to a
  real entity is coincidental. Tax office and city names are real place names.

## Türkçe özet

`tr-extract-bench`, LLM'lerin Türkçe ticari belgelerden (e-fatura, hesap ekstresi, KAP
özel durum açıklaması, kargo bildirimi) yapılandırılmış JSON çıkarma başarısını ölçen küçük
ve tekrarlanabilir bir benchmark'tır. Tüm belgeler sentetiktir ve kesin doğru cevapları
(ground truth) vardır; VKN, TCKN ve IBAN değerleri kontrol hanesi geçerli ama hayalidir.

Her belge beş varyantta üretilir: temiz, OCR hatalı, Türkçe karakterleri silinmiş,
TR/EN karışık etiketli ve alanları karıştırılmış. Puanlama alan bazındadır: tutarlar
(`1.234,56 TL`), tarihler (`17 Kasım 2026`) ve kimlik numaraları türüne göre normalize
edilir; ayrıca geçerli JSON oranı ve belgede olmayan alanlar için uydurulan değer oranı
(halüsinasyon) raporlanır. Sonuç tablosu yukarıdadır ve kayıtlı model çıktılarından
yeniden üretilir.

Çalıştırmak için: `python -m unittest discover -s tests` ve `python -m trbench score`.
Kendi modellerinizi denemek için `python -m trbench run`.

## License

MIT
