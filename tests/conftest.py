import json
from pathlib import Path

import pytest

from tadabbur.settings import get_settings

DATA = get_settings().data_dir
needs_data = pytest.mark.skipif(not (DATA / "quran.json").exists(), reason="run `make data` first")


class FakeGateway:
    """Deterministic stand-in for the LLM gateway (no network)."""
    available = True

    def __init__(self, understanding=None, rerank=None):
        self.calls = []
        self.usage = {}
        self.calls_today = 0
        self._u = understanding or {
            "language": "egyptian", "intent": "concept",
            "msa": "كيف أصبر عندما يبتليني الله بأمر صعب",
            "classical": ["الصبر على البلاء والمصائب", "الاستعانة بالصبر والصلاة عند الشدائد"],
            "english": "patience in hardship"}
        self._r = rerank

    def complete_json(self, role, prompt):
        self.calls.append(role)
        if role == "understand":
            return self._u
        if self._r is not None:
            return self._r(prompt) if callable(self._r) else self._r
        import re
        ids = re.findall(r"^\[(\d+:\d+)\]", prompt, re.M)
        return {"no_answer": False, "results": [
            {"id": ids[0], "grade": 3, "why": "تحث الآية المؤمنين على الصبر عند المصائب وتبشر الصابرين بالأجر."},
            {"id": ids[1], "grade": 2, "why": "قال تعالى يا أيها الذين آمنوا استعينوا بالصبر والصلاة إن الله مع الصابرين"},
            {"id": "999:1", "grade": 3, "why": "fake"},
            {"id": ids[0], "grade": 1, "why": "duplicate"}]}

    def embed(self, role, texts):
        raise AssertionError("no dense index in tests")


@pytest.fixture(scope="session")
def corpus():
    from tadabbur.corpus import Corpus
    return Corpus.load(DATA / "quran.json")


@pytest.fixture(scope="session")
def qqa():
    return json.loads((DATA / "qqa23.json").read_text(encoding="utf-8"))
