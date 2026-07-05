import pytest
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.scorers.text import score_text


def test_text_scorer_registered():
    assert get_scorer("text") is score_text


def test_unknown_dimension_raises():
    with pytest.raises(KeyError):
        get_scorer("does_not_exist")
