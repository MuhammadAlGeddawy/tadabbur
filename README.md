# Tadabbur | تدبّر — concept search over the Quran

Describe a meaning or concept in any language or Arabic dialect and get back the ayat that discuss it, each with a one-line reason grounded in a named tafsir. Ayat are always displayed from the canonical text by ID; the model never writes Quranic text.

> Branches: **`master`** is the MVP (this README). **`demo`** is the earlier single-page demo that runs inside Claude Artifacts.

## How it works (pipeline 1, "dialect-hardened core")
```
query ─► Understand (fast LLM)        dialect + intent; MSA rewrite + 2 Classical-vocabulary paraphrases
      ─► Retrieve                     BM25 over ayah text and Tafsir al-Muyassar (rewrites only, never raw dialect)
                                      + embedding search (raw query + rewrite)  ─► RRF ─► top 40
      ─► Rank (strong LLM)            listwise; returns ayah IDs only, grade, one-line reason, or "no answer"
      ─► Guard                        drop unknown IDs; withhold any reason with 5+ consecutive Quran words
      ─► Render                       Tanzil Uthmani text by ID + full tafsir
```
Without an API key the service runs in **keyword mode** (retrieval only), so it always works.

## LLM gateway: any provider, one config
The code calls **roles** — `understand`, `rerank`, `embed` — never vendors. [`config/models.yaml`](config/models.yaml) maps each role to models through [LiteLLM](https://github.com/BerriAI/litellm), with fallbacks. Defaults route through **OpenRouter** with a single key; switching a role to a direct OpenAI, Anthropic or Gemini key is a config edit. The gateway also gives:
- a disk cache of LLM replies (reproducible evaluation, lower cost),
- a hard daily cap on LLM calls (`TADABBUR_MAX_LLM_CALLS_PER_DAY`) with automatic fallback to keyword results,
- per-role call and token counters at `GET /api/usage`.

The default model IDs are starting points; run `make check-models` once with your key to confirm they exist on OpenRouter today.

## Quick start
```bash
make install                         # Python ≥ 3.11
make data                            # fetch sources, build data/quran.json and data/qqa23.json
cp .env.example .env                 # add OPENROUTER_API_KEY
make check-models                    # confirm model IDs
make index                           # optional: build the embedding index (~6.2k ayat, one-time)
make run                             # http://localhost:8000
```
Or with Docker: `cp .env.example .env && make docker`.

## API
| Method | Path | |
|---|---|---|
| `POST` | `/api/search` | `{"query": "..."}` → understanding, ranked ayat (id, Uthmani text, grade, reason, tafsir), notice, trace |
| `GET` | `/api/health` | corpus size, whether the LLM and the embedding index are active |
| `GET` | `/api/ayah/{surah}/{ayah}` | one ayah with its tafsir |
| `GET` | `/api/usage` | LLM calls today, per-role counters |

Per-client rate limit: `TADABBUR_RATE_LIMIT_PER_MINUTE` (default 20).

## Evaluation (Qur'an QA 2023, Task A)
Official metric — MAP@10 with the no-answer rule, at passage level. Our scorer matches the official script. Evaluation uses the published datasets only.
```bash
make eval                                                # keyword stage, no key needed
python -m tadabbur.evaluate --split dev --mode hybrid    # + embeddings
make eval-full                                           # full pipeline on dev (LLM calls are cached)
```
Run files are written to `runs/` in the official format.

| Stage | Split | MAP@10 | MRR@10 | Recall@50 (answerable) |
|---|---|---|---|---|
| Keyword (ayah + tafsir, RRF) | train+dev, 199 q | **0.213** | 0.334 | 0.592 |
| Keyword (ayah + tafsir, RRF) | dev, 25 q | 0.184 | 0.284 | 0.400 |
| Hybrid, full pipeline | dev | *run with your key* | | |

Reference on the official *test* split (different questions): best submitted system 0.2506. The keyword stage scores 0 on no-answer questions by design; the ranking step handles them.

## Project layout
```
tadabbur/      arabic.py (normalization) · retrieval.py (BM25, dense, RRF, guard) · corpus.py
               gateway.py (LiteLLM roles, cache, budget) · prompts.py · pipeline.py · api.py
               build_data.py · build_index.py · evaluate.py · metrics.py · check_models.py
config/        models.yaml — role → provider/model routing
web/           static frontend served by the API
tests/         unit + integration tests (mocked LLM; no network)
scripts/       fetch_sources.sh
```

## Tests
`make test` — 17 tests: Arabic normalization parity, metric, gateway routing/cache/budget, pipeline guard (drops fake IDs, withholds Quran quotes, renders only canonical text), API limits, and a regression floor on the keyword-stage score. CI runs them on every push.

## Data and credits
Data is **not** committed; `make data` downloads it from GitHub mirrors.
- Quran text: [Tanzil Project](https://tanzil.net), Uthmani v1.1 — displayed verbatim (CC BY 3.0).
- Tafsir: Al-Tafsir al-Muyassar (King Fahd Complex).
- Benchmark: Qur'an QA 2023 shared task — Malhas, Mansour & Elsayed, *ArabicNLP 2023*; evaluation use only.

Results are an aid to reflection (tadabbur), not a religious ruling.
