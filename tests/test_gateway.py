import types

import pytest

from tadabbur.gateway import BudgetExceeded, GatewayError, LiteLLMGateway, parse_json
from tadabbur.settings import ROOT


def test_parse_json_tolerant():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('Here:\n```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json('Sure. {"a": 3} Done.') == {"a": 3}
    with pytest.raises(GatewayError):
        parse_json("no json here")


class FakeRouter:
    def __init__(self):
        self.n = 0

    def completion(self, model, messages, **kw):
        self.n += 1
        msg = types.SimpleNamespace(content='{"ok": true, "model": "%s"}' % model)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], model=model,
                                     usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5))


def make(tmp_path, monkeypatch, max_calls=10):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    gw = LiteLLMGateway(ROOT / "config" / "models.yaml", tmp_path, True, max_calls)
    gw._router = FakeRouter()
    return gw


def test_roles_route_to_aliases_and_cache(tmp_path, monkeypatch):
    gw = make(tmp_path, monkeypatch)
    assert gw.available
    assert gw.complete_json("rerank", "p") == {"ok": True, "model": "tadabbur-rerank"}
    assert gw.complete_json("rerank", "p")["ok"]          # served from cache
    assert gw._router.n == 1
    assert gw.usage["rerank"]["calls"] == 1 and gw.usage["rerank"]["cached"] == 1
    assert gw.usage["rerank"]["tokens_in"] == 10


def test_daily_cap(tmp_path, monkeypatch):
    gw = make(tmp_path, monkeypatch, max_calls=1)
    gw.complete_json("understand", "a")
    with pytest.raises(BudgetExceeded):
        gw.complete_json("understand", "b")


def test_unavailable_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert not LiteLLMGateway(ROOT / "config" / "models.yaml", tmp_path).available
