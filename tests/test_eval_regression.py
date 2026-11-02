from conftest import needs_data

from tadabbur.gateway import NullGateway
from tadabbur.metrics import passage_mapper, score_question, summarize
from tadabbur.pipeline import Pipeline


@needs_data
def test_keyword_stage_score_does_not_regress(corpus, qqa):
    pipe, to_p = Pipeline(corpus, NullGateway()), passage_mapper(corpus, qqa["passages"])
    scores = []
    for _qid, q, rel in qqa["train"] + qqa["dev"]:
        fused, _ = pipe.retrieve(q, [q], use_dense=False, depth=300, limit=300)
        scores.append(score_question(to_p(i for i, _ in fused)[:100], rel))
    s = summarize(scores)
    assert s["map10"] >= 0.205, s     # 0.213 when written (ayah + tafsir BM25 with RRF)
