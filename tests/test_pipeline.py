from conftest import FakeGateway, needs_data

from tadabbur.gateway import NullGateway
from tadabbur.pipeline import Pipeline, parse_understanding, query_views


def test_no_keyword_search_on_raw_dialect():
    u = parse_understanding({"language": "egyptian", "msa": "m", "classical": ["c1", "c2"]})
    assert query_views("raw dialect", u) == ["m", "c1", "c2"]
    u = parse_understanding({"language": "msa", "msa": "m", "classical": []})
    assert query_views("raw", u)[0] == "raw"


def test_bad_understanding_is_sanitized():
    u = parse_understanding({"language": "klingon", "intent": "hack", "classical": "x"})
    assert u.language == "other" and u.intent == "concept" and u.classical == []


@needs_data
def test_full_pipeline_guards_and_renders_canonical_text(corpus):
    gw = FakeGateway()
    res = Pipeline(corpus, gw).search("إزاي أصبر لما ربنا يبتليني")
    assert res.mode == "full" and not res.no_answer
    assert gw.calls == ["understand", "rerank"]
    assert len(res.results) == 2                        # fake ID and duplicate dropped
    assert res.trace["dropped_ids"] == 2
    assert res.results[1].why_withheld and res.results[1].why == ""   # Quran quote withheld
    for r in res.results:
        assert r.text == corpus.uthmani[corpus.index_of[r.id]]       # text only from the corpus


@needs_data
def test_no_answer_and_ruling_notice(corpus):
    gw = FakeGateway(understanding={"language": "msa", "intent": "ruling", "msa": "حكم", "classical": []},
                     rerank={"no_answer": True, "results": []})
    res = Pipeline(corpus, gw).search("ما حكم كذا")
    assert res.no_answer and res.results == [] and "ruling" in res.notice


@needs_data
def test_keyword_mode_without_llm(corpus):
    res = Pipeline(corpus, NullGateway()).search("الصبر عند البلاء")
    assert res.mode == "keyword" and len(res.results) == 10 and res.understanding is None
