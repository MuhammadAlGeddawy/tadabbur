from conftest import FakeGateway, needs_data
from fastapi.testclient import TestClient

from tadabbur.api import create_app
from tadabbur.pipeline import Pipeline


@needs_data
def test_api_search_health_and_limits(corpus, monkeypatch):
    monkeypatch.setenv("TADABBUR_RATE_LIMIT_PER_MINUTE", "3")
    with TestClient(create_app(Pipeline(corpus, FakeGateway()))) as c:
        h = c.get("/api/health").json()
        assert h["ayat"] == 6236 and h["llm"] is True
        r = c.post("/api/search", json={"query": "الصبر"})
        assert r.status_code == 200 and r.json()["mode"] == "full"
        assert c.post("/api/search", json={"query": ""}).status_code == 422
        assert c.post("/api/search", json={"query": "x" * 301}).status_code == 422
        # invalid requests are rejected before the limiter; 3 valid searches allowed per minute
        assert c.post("/api/search", json={"query": "a"}).status_code == 200
        assert c.post("/api/search", json={"query": "b"}).status_code == 200
        assert c.post("/api/search", json={"query": "c"}).status_code == 429
        assert c.get("/api/ayah/2/286").json()["id"] == "2:286"
        assert c.get("/api/ayah/2/287").status_code == 404
        assert c.get("/").status_code == 200
