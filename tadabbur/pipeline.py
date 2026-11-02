"""Pipeline 1 (dialect-hardened core).

understand -> retrieve (BM25 x 2 fields x query views, + dense) -> RRF -> LLM listwise rerank to IDs
-> guard -> render from canonical text.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .corpus import Corpus
from .gateway import Gateway, GatewayError
from .prompts import INTENTS, LANGUAGES, rerank_prompt, understand_prompt

log = logging.getLogger(__name__)


@dataclass
class Understanding:
    language: str = "other"
    intent: str = "concept"
    msa: str = ""
    classical: list[str] = field(default_factory=list)
    english: str = ""


@dataclass
class Result:
    id: str
    surah: int
    ayah: int
    surah_name: str
    text: str
    tafsir: str
    grade: int | None = None
    why: str = ""
    why_lang: str = "ar"
    why_withheld: bool = False


@dataclass
class SearchResponse:
    query: str
    mode: str                      # "full" | "keyword"
    understanding: Understanding | None
    no_answer: bool
    notice: str
    results: list[Result]
    trace: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


def _s(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def parse_understanding(raw: Any) -> Understanding:
    raw = raw if isinstance(raw, dict) else {}
    cl = raw.get("classical")
    return Understanding(
        language=raw.get("language") if raw.get("language") in LANGUAGES else "other",
        intent=raw.get("intent") if raw.get("intent") in INTENTS else "concept",
        msa=_s(raw.get("msa")),
        classical=[c for c in (_s(x) for x in (cl if isinstance(cl, list) else [])) if c][:3],
        english=_s(raw.get("english")),
    )


def query_views(query: str, u: Understanding) -> list[str]:
    """Lexical query views. Keyword search never runs on raw dialect text."""
    views = ([query] if u.language == "msa" else []) + [u.msa, *u.classical]
    seen, out = set(), []
    for v in views:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


NOTICES = {
    "ruling": "This looks like a request for a religious ruling. Tadabbur shows ayat related to the topic with their tafsir; it does not issue rulings. Please ask a qualified scholar.",
    "out_of_scope": "This doesn't look like a meaning or theme to search for in the Quran, so results may be unrelated.",
}


class Pipeline:
    def __init__(self, corpus: Corpus, gateway: Gateway, candidates: int = 40):
        self.c = corpus
        self.gw = gateway
        self.k = candidates

    # ---- stages ----
    def understand(self, query: str) -> Understanding:
        return parse_understanding(self.gw.complete_json("understand", understand_prompt(query)))

    def retrieve(self, query: str, views: list[str], use_dense: bool = True, depth: int = 200, limit: int | None = None):
        limit = limit or self.k
        lex = self.c.lexical_lists(views or [query], depth)
        lists = [l for _, _, l in lex]
        trace = {"views": views or [query], "lexical_lists": len(lex), "dense": False}
        if use_dense and self.c.dense is not None and self.gw.available:
            dense_queries = list(dict.fromkeys([query, *views[:1]]))  # raw query + MSA rewrite
            try:
                vecs = self.gw.embed("embed", dense_queries)
                for v in vecs:
                    lists.append(self.c.dense.search(v, depth))
                trace["dense"] = True
            except GatewayError as e:
                log.warning("Dense retrieval skipped: %s", e)
        return self.c.fuse(lists, limit), trace

    def rerank(self, query: str, u: Understanding, fused) -> tuple[bool, list[Result], dict]:
        cands = []
        for i, _ in fused:
            taf = " ".join(self.c.tafsir[i].split())[:380]
            cands.append((self.c.ids[i], self.c.uthmani[i], taf))
        lang = "en" if u.language == "english" else "ar"
        raw = self.gw.complete_json("rerank", rerank_prompt(query, u.msa or query, cands, lang))
        allowed = {self.c.ids[i]: i for i, _ in fused}
        seen, out, dropped, withheld = set(), [], 0, 0
        items = raw.get("results") if isinstance(raw, dict) and isinstance(raw.get("results"), list) else []
        for x in items:
            cid = _s((x or {}).get("id")) if isinstance(x, dict) else ""
            if cid not in allowed or cid in seen:
                dropped += 1
                continue
            seen.add(cid)
            why = _s(x.get("why"))
            hits = self.c.guard.check(why) if why else []
            if hits:
                withheld += 1
                why = ""
            try:
                grade = int(x.get("grade"))
            except (TypeError, ValueError):
                grade = 1
            r = self._result(allowed[cid])
            r.grade, r.why, r.why_lang, r.why_withheld = (grade if grade in (1, 2, 3) else 1), why, lang, bool(hits)
            out.append(r)
        no_answer = bool(isinstance(raw, dict) and raw.get("no_answer")) and not out
        return no_answer, out[:10], {"dropped_ids": dropped, "withheld_reasons": withheld}

    def _result(self, i: int) -> Result:
        s, a = self.c.surah_ayah(i)
        return Result(id=self.c.ids[i], surah=s, ayah=a, surah_name=self.c.names[s - 1],
                      text=self.c.uthmani[i], tafsir=self.c.tafsir[i])

    # ---- entry points ----
    def keyword_search(self, query: str, limit: int = 10) -> SearchResponse:
        t = time.perf_counter()
        fused, trace = self.retrieve(query, [query], use_dense=False, limit=limit)
        trace["timings_ms"] = {"retrieve": round((time.perf_counter() - t) * 1000)}
        return SearchResponse(query, "keyword", None, not fused, "", [self._result(i) for i, _ in fused], trace)

    def search(self, query: str) -> SearchResponse:
        if not self.gw.available:
            return self.keyword_search(query)
        T: dict[str, int] = {}
        t = time.perf_counter()
        u = self.understand(query)
        T["understand"] = round((time.perf_counter() - t) * 1000)

        t = time.perf_counter()
        views = query_views(query, u)
        fused, trace = self.retrieve(query, views)
        T["retrieve"] = round((time.perf_counter() - t) * 1000)
        trace["candidates"] = len(fused)

        no_answer, results = True, []
        if fused:
            t = time.perf_counter()
            no_answer, results, g = self.rerank(query, u, fused)
            T["rerank"] = round((time.perf_counter() - t) * 1000)
            trace.update(g)
        trace["timings_ms"] = T
        trace["fused_ids"] = [self.c.ids[i] for i, _ in fused]
        return SearchResponse(query, "full", u, no_answer, NOTICES.get(u.intent, ""), results, trace)
