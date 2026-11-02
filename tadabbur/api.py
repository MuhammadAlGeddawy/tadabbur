"""HTTP API and web app.

    uvicorn tadabbur.api:app --port 8000
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .corpus import Corpus
from .gateway import BudgetExceeded, GatewayError, build_gateway
from .pipeline import Pipeline
from .settings import ROOT, get_settings

log = logging.getLogger("tadabbur.api")
WEB = ROOT / "web"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


def create_app(pipeline: Pipeline | None = None) -> FastAPI:
    settings = get_settings()
    state: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if pipeline is not None:
            state["pipe"] = pipeline
        else:
            if not settings.quran_path.exists():
                raise RuntimeError(f"{settings.quran_path} not found. Run `make data` first.")
            corpus = Corpus.load(settings.quran_path, settings.index_dir)
            state["pipe"] = Pipeline(corpus, build_gateway(settings), settings.candidates)
            log.info("Corpus loaded: %d ayat; dense index: %s; LLM: %s", len(corpus.ids),
                     corpus.dense.model if corpus.dense else "none", state["pipe"].gw.available)
        yield

    app = FastAPI(title="Tadabbur", version="0.2.0", lifespan=lifespan)
    limiter = RateLimiter(settings.rate_limit_per_minute)

    @app.get("/api/health")
    def health():
        p: Pipeline = state["pipe"]
        return {"status": "ok", "ayat": len(p.c.ids), "llm": p.gw.available,
                "dense": p.c.dense.model if p.c.dense else None}

    @app.post("/api/search")
    async def search(req: SearchRequest, request: Request):
        client = request.client.host if request.client else "anon"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many searches. Wait a minute and try again.")
        p: Pipeline = state["pipe"]
        q = " ".join(req.query.split())
        try:
            res = await run_in_threadpool(p.search, q)
        except BudgetExceeded:
            res = await run_in_threadpool(p.keyword_search, q)
            res.notice = "The daily limit for AI-ranked searches has been reached, so these are keyword results."
        except GatewayError as e:
            log.warning("LLM step failed: %s", e)
            res = await run_in_threadpool(p.keyword_search, q)
            res.notice = "The AI ranking step is unavailable right now, so these are keyword results."
        return res.to_dict()

    @app.get("/api/ayah/{surah}/{ayah}")
    def ayah(surah: int, ayah: int):
        p: Pipeline = state["pipe"]
        if not (1 <= surah <= 114) or not (1 <= ayah <= p.c.counts[surah - 1]):
            raise HTTPException(404, "No such ayah.")
        r = p._result(p.c.idx(surah, ayah))
        return r.__dict__

    @app.get("/api/usage")
    def usage():
        gw = state["pipe"].gw
        return {"calls_today": getattr(gw, "calls_today", 0), "by_role": getattr(gw, "usage", {})}

    if WEB.exists():
        app.mount("/static", StaticFiles(directory=WEB), name="static")

        @app.get("/")
        def index():
            return FileResponse(WEB / "index.html")

    return app


app = create_app()
