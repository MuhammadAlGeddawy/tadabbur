"""LLM gateway: role-based model names routed by LiteLLM to any provider (OpenRouter by default).

Code asks for a ROLE (`understand`, `rerank`, `embed`); `config/models.yaml` decides which provider and
model serve it, with fallbacks. Moving a role from OpenRouter to a direct OpenAI or Anthropic key is a
config change, not a code change.

Also provides: a disk cache (reproducible evaluation, lower cost), a daily cap on LLM calls, and usage
counters per role.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Protocol

import yaml

log = logging.getLogger(__name__)


class GatewayError(RuntimeError):
    pass


class BudgetExceeded(GatewayError):
    pass


class Gateway(Protocol):
    def complete_json(self, role: str, prompt: str) -> Any: ...
    def embed(self, role: str, texts: list[str]) -> list[list[float]]: ...
    @property
    def available(self) -> bool: ...


def parse_json(text: str) -> Any:
    """Tolerant JSON extraction: whole reply, a fenced block, or the outermost {...} / [...]."""
    t = (text or "").strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    for o, c in (("{", "}"), ("[", "]")):
        a, b = t.find(o), t.rfind(c)
        if a != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:
                continue
    raise GatewayError("The model reply did not contain valid JSON.")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("os.environ/"):
        return os.getenv(value.split("/", 1)[1], "")
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


class LiteLLMGateway:
    def __init__(self, config_path: Path, cache_dir: Path | None = None, cache_enabled: bool = True,
                 max_calls_per_day: int = 2000):
        cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        self.roles: dict[str, str] = cfg.get("roles", {})
        self.settings: dict[str, Any] = cfg.get("settings", {})
        self.model_list = _expand_env(cfg["model_list"])
        self.fallbacks = cfg.get("fallbacks", [])
        self.cache_dir = cache_dir if cache_enabled else None
        self.max_calls = max_calls_per_day
        self._lock = threading.Lock()
        self._day = dt.date.today().isoformat()
        self.usage: dict[str, dict[str, int]] = {}
        self.calls_today = 0
        self._router = None

    # ---- availability ----
    @property
    def available(self) -> bool:
        return any(m.get("litellm_params", {}).get("api_key") for m in self.model_list)

    def _get_router(self):
        if self._router is None:
            from litellm import Router  # imported lazily: heavy import
            self._router = Router(model_list=self.model_list, fallbacks=self.fallbacks,
                                  num_retries=int(self.settings.get("num_retries", 2)),
                                  timeout=float(self.settings.get("timeout", 60)))
        return self._router

    # ---- budget / usage ----
    def _count(self, role: str, cached: bool, tokens_in: int = 0, tokens_out: int = 0) -> None:
        with self._lock:
            today = dt.date.today().isoformat()
            if today != self._day:
                self._day, self.calls_today = today, 0
            u = self.usage.setdefault(role, {"calls": 0, "cached": 0, "tokens_in": 0, "tokens_out": 0})
            if cached:
                u["cached"] += 1
                return
            if self.calls_today >= self.max_calls:
                raise BudgetExceeded("Daily LLM call limit reached.")
            self.calls_today += 1
            u["calls"] += 1
            u["tokens_in"] += tokens_in
            u["tokens_out"] += tokens_out

    # ---- cache ----
    def _cache_path(self, kind: str, role: str, payload: str) -> Path | None:
        if not self.cache_dir:
            return None
        h = hashlib.sha256(f"{kind}|{self.roles.get(role, role)}|{payload}".encode()).hexdigest()
        return self.cache_dir / kind / h[:2] / f"{h}.json"

    def _cache_get(self, p: Path | None):
        if p and p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _cache_put(self, p: Path | None, value) -> None:
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    # ---- calls ----
    def complete_json(self, role: str, prompt: str) -> Any:
        alias = self.roles.get(role, role)
        cp = self._cache_path("chat", role, prompt)
        hit = self._cache_get(cp)
        if hit is not None:
            self._count(role, cached=True)
            return parse_json(hit["text"])
        self._count(role, cached=False)  # raises BudgetExceeded before spending
        resp = self._get_router().completion(model=alias, messages=[{"role": "user", "content": prompt}],
                                             temperature=float(self.settings.get("temperature", 0)))
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        with self._lock:
            u = self.usage[role]
            u["tokens_in"] += int(getattr(usage, "prompt_tokens", 0) or 0)
            u["tokens_out"] += int(getattr(usage, "completion_tokens", 0) or 0)
        value = parse_json(text)  # only cache replies that parse
        self._cache_put(cp, {"text": text, "model": getattr(resp, "model", alias)})
        return value

    def embed(self, role: str, texts: list[str]) -> list[list[float]]:
        alias = self.roles.get(role, role)
        cp = self._cache_path("embed", role, json.dumps(texts, ensure_ascii=False))
        hit = self._cache_get(cp)
        if hit is not None:
            self._count(role, cached=True)
            return hit
        self._count(role, cached=False)
        resp = self._get_router().embedding(model=alias, input=texts)
        vecs = [d["embedding"] if isinstance(d, dict) else d.embedding for d in resp.data]
        self._cache_put(cp, vecs)
        return vecs


class NullGateway:
    """Used when no API key is configured: the service runs in keyword-only mode."""
    available = False
    usage: dict = {}
    calls_today = 0

    def complete_json(self, role: str, prompt: str) -> Any:
        raise GatewayError("No LLM provider is configured.")

    def embed(self, role: str, texts: list[str]) -> list[list[float]]:
        raise GatewayError("No embedding provider is configured.")


def build_gateway(settings) -> Gateway:
    gw = LiteLLMGateway(settings.models_config, settings.cache_dir, settings.cache_enabled, settings.max_llm_calls_per_day)
    if not gw.available:
        log.warning("No API key configured (set OPENROUTER_API_KEY). Running in keyword-only mode.")
        return NullGateway()
    return gw
