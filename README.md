# Tadabbur | تدبّر — concept search over the Quran

Describe a meaning or concept in any language or Arabic dialect and get back the ayat that discuss it, each with a short reason grounded in a named tafsir. This repository holds the **pipeline 1 demo** (the "dialect-hardened core" chosen in the project's pipeline review).

## Pipeline
1. **Understand** (LLM, fast tier): detect language/dialect and intent; write an MSA rewrite and two paraphrases in Classical Quranic vocabulary. The raw query is kept for ranking.
2. **Retrieve** (no model): BM25 over two fields for all 6,236 ayat — Uthmani ayah text and Tafsir al-Muyassar — with Arabic normalization that matches Uthmani spelling to modern spelling, light stemming, and Reciprocal Rank Fusion across views × fields. Keyword search never runs on raw dialect text.
3. **Rank** (LLM): listwise over the top 40; returns **ayah IDs only**, a grade (direct / implicit-story / related) and a one-line reason, or "no relevant ayah".
4. **Guard**: drops IDs outside the candidate set; withholds any reason that contains 5 consecutive words found in the Quran (spelling-insensitive, across ayah boundaries).
5. **Render**: ayat are displayed by ID from the Tanzil Uthmani text — never from model output.

All retrieval and guard logic lives in [`site/retrieval.js`](site/retrieval.js) and is shared by the page and the offline evaluation.

## Results (Qur'an QA 2023, Task A)
Official metric (MAP@10 with the no-answer rule), ayah results mapped to the task's 1,266 thematic passages. Our scorer reproduces the official script. Keyword stage only:

| Config | MAP@10 (train+dev, 199 q) | MRR | Recall@50 (answerable) |
|---|---|---|---|
| Ayah text only | 0.163 | 0.266 | 0.459 |
| Tafsir only | 0.193 | 0.308 | 0.558 |
| **Ayah + tafsir (RRF)** | **0.213** | 0.344 | 0.592 |

For reference, on the official *test* set (different questions) the best submitted system scored 0.2506. The full pipeline with LLM ranking is scored from the demo's **Benchmark** tab.

## Run it
```bash
bash scripts/fetch_sources.sh        # download sources into data-src/
python3 build/build_data.py          # build site/data/*.json (with integrity checks)
node eval/eval_recall.js             # offline evaluation of the retrieval stage
python3 scripts/serve_local.py       # keyword-only local view at http://127.0.0.1:8000/local.html
```
`site/index.html` is written for Claude Artifacts, which supplies the LLM calls (the `sample` capability). A standalone backend with an LLM gateway (LiteLLM over OpenRouter) is planned.

Tests: `pip install playwright && python3 eval/browser_test.py` runs the page headless with a mocked LLM, including the guard.

## Known gaps
- No dense embedding retrieval yet.
- Franco-Arabic is handled by the understanding call, without a dedicated transliteration step.
- Data comes from GitHub mirrors of the original providers.

## Data and credits
Data is **not** included in this repository; `scripts/fetch_sources.sh` downloads it.
- Quran text: [Tanzil Project](https://tanzil.net), Uthmani v1.1 — displayed verbatim (CC BY 3.0), via the `semnan-university-ai/checksum-quran` mirror.
- Tafsir: Al-Tafsir al-Muyassar (King Fahd Complex), via the `spa5k/tafsir_api` mirror.
- Benchmark: Qur'an QA 2023 shared task — Malhas, Mansour & Elsayed, *ArabicNLP 2023* — via the `ghazaleh-mahmoodi/quran-qa_2023_shared-task` mirror; evaluation use only.

Results are an aid to reflection (tadabbur), not a religious ruling.
