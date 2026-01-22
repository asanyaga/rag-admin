class AuthenticationError(Exception):
    """Raised when authentication fails (invalid credentials, expired token, etc.)"""
    pass


class AccountLockedError(Exception):
    """Raised when account is locked due to too many failed login attempts"""
    pass


class ConflictError(Exception):
    """Raised when a resource already exists (e.g., duplicate email)"""
    pass
