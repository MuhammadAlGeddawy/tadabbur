"""The Quran corpus: canonical text, tafsir, lexical and dense indexes, and the guard."""
from __future__ import annotations

import json
import logging
from functools import cached_property
from pathlib import Path

import numpy as np

from .arabic import normalize, tokens
from .retrieval import BM25, DenseIndex, QuranGuard, Ranked, rrf

log = logging.getLogger(__name__)


def dense_doc_text(name: str, ayah_uthmani: str, tafsir: str) -> str:
    """Text embedded for each ayah: surah name, ayah (diacritics removed) and its tafsir."""
    return f"سورة {name}: {normalize(ayah_uthmani)}\nالتفسير الميسر: {tafsir}"


class Corpus:
    def __init__(self, quran: dict, dense: DenseIndex | None = None):
        self.q = quran
        self.names: list[str] = quran["names"]
        self.counts: list[int] = quran["counts"]
        self.uthmani: list[str] = quran["uthmani"]
        self.tafsir: list[str] = quran["muyassar"]
        self.ids: list[str] = []
        self.start = [0]
        for si, c in enumerate(self.counts):
            self.ids.extend(f"{si + 1}:{a}" for a in range(1, c + 1))
            self.start.append(self.start[-1] + c)
        self.index_of = {i: k for k, i in enumerate(self.ids)}
        self.ayah_bm25 = BM25([tokens(t) for t in self.uthmani])
        self.tafsir_bm25 = BM25([tokens(t) for t in self.tafsir])
        self.dense = dense

    @classmethod
    def load(cls, quran_path: Path, index_dir: Path | None = None) -> "Corpus":
        quran = json.loads(Path(quran_path).read_text(encoding="utf-8"))
        dense = None
        if index_dir:
            emb, meta = index_dir / "embeddings.npy", index_dir / "embeddings.json"
            if emb.exists() and meta.exists():
                m = json.loads(meta.read_text(encoding="utf-8"))
                if m.get("n") == sum(quran["counts"]) and m.get("sha256_uthmani") == quran.get("sha256_uthmani"):
                    dense = DenseIndex(np.load(emb), m.get("model", "?"))
                else:
                    log.warning("Dense index does not match the corpus; ignoring it. Rebuild with `make index`.")
        return cls(quran, dense)

    @cached_property
    def guard(self) -> QuranGuard:
        return QuranGuard(self.uthmani, self.counts)

    def idx(self, surah: int, ayah: int) -> int:
        return self.start[surah - 1] + ayah - 1

    def surah_ayah(self, i: int) -> tuple[int, int]:
        s, a = self.ids[i].split(":")
        return int(s), int(a)

    def dense_texts(self) -> list[str]:
        out = []
        for i in range(len(self.ids)):
            s, _ = self.surah_ayah(i)
            out.append(dense_doc_text(self.names[s - 1], self.uthmani[i], self.tafsir[i]))
        return out

    def lexical_lists(self, views: list[str], depth: int = 200, fields=("ayah", "tafsir")) -> list[tuple[str, str, Ranked]]:
        out = []
        for v in views:
            qt = tokens(v)
            if not qt:
                continue
            if "ayah" in fields:
                out.append((v, "ayah", self.ayah_bm25.search(qt, depth)))
            if "tafsir" in fields:
                out.append((v, "tafsir", self.tafsir_bm25.search(qt, depth)))
        return out

    def fuse(self, lists: list[Ranked], limit: int) -> Ranked:
        return rrf(lists, 60, limit)
