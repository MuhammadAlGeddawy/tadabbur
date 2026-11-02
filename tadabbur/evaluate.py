"""Evaluate on Qur'an QA 2023 Task A with the official metric.

    python -m tadabbur.evaluate --split dev --mode keyword   # BM25 only, no API key needed
    python -m tadabbur.evaluate --split dev --mode hybrid    # + dense retrieval (needs the index)
    python -m tadabbur.evaluate --split dev --mode full      # + LLM understanding and reranking

Writes an official-format run file to runs/ and prints MAP@10, MRR@10 and recall.
LLM replies are cached on disk, so re-running costs nothing.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .corpus import Corpus
from .gateway import GatewayError, build_gateway
from .metrics import passage_mapper, score_question, summarize
from .pipeline import Pipeline, query_views
from .settings import ROOT, get_settings

log = logging.getLogger("tadabbur.evaluate")


def run(split: str, mode: str, limit: int | None = None) -> dict:
    s = get_settings()
    corpus = Corpus.load(s.quran_path, s.index_dir)
    qqa = json.loads(s.qqa_path.read_text(encoding="utf-8"))
    questions = qqa["train"] + qqa["dev"] if split == "all" else qqa[split]
    questions = questions[:limit] if limit else questions
    gw = build_gateway(s)
    if mode in ("hybrid", "full") and not gw.available:
        raise SystemExit(f"--mode {mode} needs an API key (OPENROUTER_API_KEY).")
    if mode == "hybrid" and corpus.dense is None:
        raise SystemExit("--mode hybrid needs the dense index. Run `make index` first.")
    pipe = Pipeline(corpus, gw, s.candidates)
    to_p = passage_mapper(corpus, qqa["passages"])

    scores, lines, errors = [], [], 0
    for n, (qid, q, rel) in enumerate(questions, 1):
        try:
            if mode == "keyword":
                fused, _ = pipe.retrieve(q, [q], use_dense=False, depth=300, limit=300)
                ranked = to_p(i for i, _ in fused)
            elif mode == "hybrid":
                fused, _ = pipe.retrieve(q, [q], use_dense=True, depth=300, limit=300)
                ranked = to_p(i for i, _ in fused)
            else:
                u = pipe.understand(q)
                views = query_views(q, u)
                fused, _ = pipe.retrieve(q, views, limit=s.candidates)
                no_answer, results, _ = pipe.rerank(q, u, fused) if fused else (True, [], {})
                if no_answer:
                    ranked = ["-1"]
                else:
                    top = [corpus.index_of[r.id] for r in sorted(results, key=lambda r: -(r.grade or 0))]
                    rest = [i for i, _ in fused if i not in top]
                    ranked = to_p(top + rest)
        except GatewayError as e:
            errors += 1
            log.warning("q%s failed: %s", qid, e)
            ranked = []
        sc = score_question(ranked[:100], rel)
        scores.append(sc)
        for r, pid in enumerate(ranked[:10]):
            lines.append(f"{qid}\tQ0\t{pid}\t{r + 1}\t{10 - r}\ttadabbur")
        if mode == "full":
            log.info("%d/%d q%s AP@10=%.3f", n, len(questions), qid, sc["ap10"])

    out = summarize(scores) | {"split": split, "mode": mode, "errors": errors}
    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    (runs / f"tadab_{split}{mode}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if hasattr(gw, "usage"):
        out["llm_usage"] = gw.usage
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["train", "dev", "all"], default="dev")
    ap.add_argument("--mode", choices=["keyword", "hybrid", "full"], default="keyword")
    ap.add_argument("--limit", type=int, help="only the first N questions")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    res = run(args.split, args.mode, args.limit)
    print(json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in res.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
