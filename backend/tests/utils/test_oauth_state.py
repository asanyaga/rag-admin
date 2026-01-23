import time
from datetime import datetime, timedelta

import pytest

from app.utils.oauth_state import cleanup_expired_states, generate_state, validate_state


def test_generate_state_creates_unique_values():
    """State generation should create unique values."""
    state1 = generate_state()
    state2 = generate_state()

    assert state1 != state2
    assert len(state1) > 0
    assert len(state2) > 0


def test_validate_state_accepts_valid_state():
    """Valid state should pass validation."""
    state = generate_state()
    assert validate_state(state) is True


def test_validate_state_rejects_invalid_state():
    """Invalid state should fail validation."""
    assert validate_state("invalid-state-12345") is False


def test_validate_state_consumes_state_on_use():
    """Used state should fail second validation (consumed)."""
    state = generate_state()

    # First validation should succeed
    assert validate_state(state) is True

    # Second validation should fail (state consumed)
    assert validate_state(state) is False


def test_validate_state_rejects_expired_state():
    """Expired state should fail validation."""
    from app.utils import oauth_state

    # Generate state
    state = generate_state()

    # Manually expire the state by setting expiry to past
    oauth_state._state_store[state] = datetime.utcnow() - timedelta(minutes=1)

    # Validation should fail
    assert validate_state(state) is False


def test_cleanup_expired_states():
    """Cleanup should remove expired states."""
    from app.utils import oauth_state

    # Clear any existing states from previous tests
    oauth_state._state_store.clear()

    # Generate some states
    state1 = generate_state()
    state2 = generate_state()
    state3 = generate_state()

    # Expire state1 and state2
    oauth_state._state_store[state1] = datetime.utcnow() - timedelta(minutes=1)
    oauth_state._state_store[state2] = datetime.utcnow() - timedelta(minutes=1)

    # state3 remains valid
    # Store should have 3 items
    assert len(oauth_state._state_store) == 3

    # Run cleanup
    cleanup_expired_states()

    # Only state3 should remain
    assert len(oauth_state._state_store) == 1
    assert state3 in oauth_state._state_store


def test_state_format_is_url_safe():
    """Generated state should be URL-safe."""
    state = generate_state()

    # URL-safe base64 uses only alphanumeric, dash, and underscore
    assert all(c.isalnum() or c in '-_' for c in state)
