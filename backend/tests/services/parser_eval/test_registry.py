import pytest
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.scorers.text import score_text


def test_text_scorer_spec_signature():
    spec = get_scorer("text")
    assert spec.fn is score_text
    assert spec.primary == "similarity"
    assert set(spec.emits) == {"similarity", "omission", "hallucination"}


def test_unknown_dimension_raises():
    with pytest.raises(KeyError):
        get_scorer("does_not_exist")
