"""Qur'an QA 2023 Task A scoring (passage level), matching the official evaluation script:
AP@10 as trec `map_cut_10` (divided by the number of relevant passages), reciprocal rank,
and the no-answer rule (a no-answer question scores 1 only if the run is exactly ["-1"])."""
from __future__ import annotations

from typing import Iterable, Sequence


def passage_mapper(corpus, passages: Sequence[Sequence]):
    of_ayah = [-1] * len(corpus.ids)
    for pi, (_pid, s, a1, a2) in enumerate(passages):
        for a in range(a1, a2 + 1):
            of_ayah[corpus.idx(s, a)] = pi

    def to_passages(ayah_indices: Iterable[int]) -> list[str]:
        seen, out = set(), []
        for i in ayah_indices:
            p = of_ayah[i]
            if p >= 0 and p not in seen:
                seen.add(p)
                out.append(passages[p][0])
        return out

    return to_passages


def score_question(ranked: list[str], rel: list[str]) -> dict:
    if rel == ["-1"]:
        ok = 1.0 if ranked == ["-1"] else 0.0
        return {"ap10": ok, "rr10": ok, "r10": ok, "r50": ok, "zero": True}
    R = set(rel)
    hits, sum_p = 0, 0.0
    for k, d in enumerate(ranked[:10]):
        if d in R:
            hits += 1
            sum_p += hits / (k + 1)
    rr10 = next((1 / (k + 1) for k, d in enumerate(ranked[:10]) if d in R), 0.0)
    recall = lambda K: len([d for d in ranked[:K] if d in R]) / len(R)
    return {"ap10": sum_p / len(R), "rr10": rr10, "r10": recall(10), "r50": recall(50), "zero": False}


def summarize(scores: list[dict]) -> dict:
    def mean(key, pred=lambda s: True):
        xs = [s[key] for s in scores if pred(s)]
        return sum(xs) / len(xs) if xs else 0.0
    return {
        "n": len(scores),
        "map10": mean("ap10"),
        "mrr10": mean("rr10"),
        "recall10_answerable": mean("r10", lambda s: not s["zero"]),
        "recall50_answerable": mean("r50", lambda s: not s["zero"]),
        "no_answer_accuracy": mean("ap10", lambda s: s["zero"]),
    }
