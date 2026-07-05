from app.models.parser_eval import (
    ParserEvalCase, ParserEvalTarget, ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalRunStatus,
)


def test_dimension_and_status_enums():
    assert ParserEvalDimension.text.value == "text"
    assert ParserEvalRunStatus.pending.value == "pending"


def test_tablenames():
    assert ParserEvalCase.__tablename__ == "parser_eval_cases"
    assert ParserEvalTarget.__tablename__ == "parser_eval_targets"
    assert ParserEvalRun.__tablename__ == "parser_eval_runs"
    assert ParserEvalResult.__tablename__ == "parser_eval_results"


def test_result_unique_constraint_present():
    names = {c.name for c in ParserEvalResult.__table__.constraints}
    assert "uq_parser_eval_results_run_case_parser_dim" in names
