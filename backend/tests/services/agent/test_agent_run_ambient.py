from uuid import uuid4

from app.services.agent.agent_run_service import _with_ambient


def test_with_ambient_injects_project_and_user_as_str():
    project_id = uuid4()
    user_id = uuid4()
    initial_state = {"foo": "bar"}

    result = _with_ambient(initial_state, project_id, user_id)

    assert result["project_id"] == str(project_id)
    assert result["user_id"] == str(user_id)
    assert isinstance(result["project_id"], str)
    assert isinstance(result["user_id"], str)
    assert result["foo"] == "bar"


def test_with_ambient_does_not_mutate_input_state():
    project_id = uuid4()
    user_id = uuid4()
    initial_state = {"foo": "bar"}

    result = _with_ambient(initial_state, project_id, user_id)

    # persisted record must stay free of ambient keys
    assert initial_state == {"foo": "bar"}
    assert "project_id" not in initial_state
    assert "user_id" not in initial_state
    # returned dict is a new object, not the same reference
    assert result is not initial_state
