from tadabbur.metrics import score_question, summarize


def test_ap10_divides_by_all_relevant():
    s = score_question(["a", "x", "b"], ["a", "b", "c", "d"])
    assert abs(s["ap10"] - (1 + 2 / 3) / 4) < 1e-9
    assert s["rr10"] == 1.0


def test_no_answer_rule():
    assert score_question(["-1"], ["-1"])["ap10"] == 1.0
    assert score_question(["-1", "x"], ["-1"])["ap10"] == 0.0
    assert score_question(["x"], ["-1"])["ap10"] == 0.0


def test_summarize_separates_answerable_recall():
    s = summarize([score_question(["a"], ["a"]), score_question(["-1"], ["-1"])])
    assert s["map10"] == 1.0 and s["recall10_answerable"] == 1.0 and s["no_answer_accuracy"] == 1.0
