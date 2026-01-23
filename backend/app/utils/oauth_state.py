import secrets
from datetime import datetime, timedelta

# In-memory store (replace with Redis in production)
_state_store: dict[str, datetime] = {}


def generate_state() -> str:
    """Generate random state, store with expiry."""
    state = secrets.token_urlsafe(32)
    _state_store[state] = datetime.utcnow() + timedelta(minutes=10)
    return state


def validate_state(state: str) -> bool:
    """Check state exists and not expired. Consume on use."""
    if state not in _state_store:
        return False
    expiry = _state_store.pop(state)
    return datetime.utcnow() < expiry


def cleanup_expired_states() -> None:
    """Remove expired states. Call periodically."""
    now = datetime.utcnow()
    expired = [s for s, exp in _state_store.items() if exp < now]
    for s in expired:
        _state_store.pop(s, None)
