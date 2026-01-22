import pytest

from app.utils.password import hash_password, validate_password_strength, verify_password


def test_hash_password():
    password = "TestPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$")  # bcrypt identifier
    assert len(hashed) > 50


def test_verify_password_correct():
    password = "TestPassword123!"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    password = "TestPassword123!"
    hashed = hash_password(password)

    assert verify_password("WrongPassword123!", hashed) is False


def test_validate_password_strength_valid():
    password = "ValidPass123!"
    is_valid, error = validate_password_strength(password)

    assert is_valid is True
    assert error is None


def test_validate_password_strength_too_short():
    password = "Short1!"
    is_valid, error = validate_password_strength(password)

    assert is_valid is False
    assert "at least 8 characters" in error


def test_validate_password_strength_no_uppercase():
    password = "lowercase123!"
    is_valid, error = validate_password_strength(password)

    assert is_valid is False
    assert "uppercase letter" in error


def test_validate_password_strength_no_lowercase():
    password = "UPPERCASE123!"
    is_valid, error = validate_password_strength(password)

    assert is_valid is False
    assert "lowercase letter" in error


def test_validate_password_strength_no_number():
    password = "NoNumbers!"
    is_valid, error = validate_password_strength(password)

    assert is_valid is False
    assert "number" in error


def test_validate_password_strength_no_special():
    password = "NoSpecial123"
    is_valid, error = validate_password_strength(password)

    assert is_valid is False
    assert "special character" in error


def test_hash_password_different_salts():
    """Test that the same password hashed twice produces different hashes."""
    password = "TestPassword123!"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
