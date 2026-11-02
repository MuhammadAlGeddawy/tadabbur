"""Lexical (BM25) and dense retrieval, Reciprocal Rank Fusion, and the Quran-quote guard."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Iterable, Sequence

import numpy as np

from .arabic import guard_key, tokens

Ranked = list[tuple[int, float]]


class BM25:
    def __init__(self, docs_tokens: Sequence[Sequence[str]], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b, self.N = k1, b, len(docs_tokens)
        self.len = np.array([len(t) for t in docs_tokens], dtype=np.float64)
        self.avg = float(self.len.mean()) if self.N else 0.0
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, toks in enumerate(docs_tokens):
            for t, c in Counter(toks).items():
                self.post[t].append((i, c))
        self.df = {t: len(p) for t, p in self.post.items()}

    def idf(self, t: str) -> float:
        d = self.df.get(t, 0)
        return math.log(1 + (self.N - d + 0.5) / (d + 0.5))

    def search(self, q_tokens: Iterable[str], k: int = 100) -> Ranked:
        scores: dict[int, float] = defaultdict(float)
        seen = set()
        for t in q_tokens:
            if t in seen or t not in self.post:
                continue
            seen.add(t)
            idf = self.idf(t)
            for i, c in self.post[t]:
                scores[i] += idf * (c * (self.k1 + 1)) / (c + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        # Stable order: score desc, then doc index asc (matches the JS implementation's insertion order on ties)
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]


class DenseIndex:
    """Cosine search over L2-normalized embeddings stored as a float32 matrix."""

    def __init__(self, matrix: np.ndarray, model: str):
        self.m = matrix.astype(np.float32)
        self.model = model

    def search(self, query_vec: Sequence[float], k: int = 100) -> Ranked:
        q = np.asarray(query_vec, dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-12)
        s = self.m @ q
        idx = np.argpartition(-s, min(k, len(s) - 1))[:k]
        idx = idx[np.argsort(-s[idx])]
        return [(int(i), float(s[i])) for i in idx]


def rrf(lists: Iterable[Ranked], k: int = 60, limit: int = 100) -> Ranked:
    agg: dict[int, float] = defaultdict(float)
    order: dict[int, int] = {}
    for l in lists:
        for r, (i, _) in enumerate(l):
            agg[i] += 1.0 / (k + r + 1)
            order.setdefault(i, len(order))
    return sorted(agg.items(), key=lambda x: (-x[1], order[x[0]]))[:limit]


class QuranGuard:
    """Flags any run of n consecutive words that appears in the Quran (spelling-insensitive,
    across ayah boundaries within a surah)."""

    def __init__(self, uthmani: Sequence[str], counts: Sequence[int], n: int = 5):
        self.n = n
        self.grams: set[str] = set()
        k = 0
        for c in counts:
            words: list[str] = []
            for _ in range(c):
                words.extend(guard_key(uthmani[k]))
                k += 1
            for i in range(len(words) - n + 1):
                self.grams.add(" ".join(words[i:i + n]))

    def check(self, text: str) -> list[str]:
        w = guard_key(text)
        hits = {" ".join(w[i:i + self.n]) for i in range(len(w) - self.n + 1)}
        return sorted(h for h in hits if h in self.grams)


def tokenize_all(texts: Sequence[str]) -> list[list[str]]:
    return [tokens(t) for t in texts]
