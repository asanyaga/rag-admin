import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newuser@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "New User"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 30 * 60
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["full_name"] == "New User"
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    # First signup
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "duplicate@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
        }
    )

    # Second signup with same email
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "duplicate@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
        }
    )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signup_weak_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "weak@example.com",
            "password": "weak",
            "password_confirm": "weak",
        }
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_signup_password_mismatch(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "mismatch@example.com",
            "password": "ValidPass123!",
            "password_confirm": "DifferentPass123!",
        }
    )

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_signin_success(client: AsyncClient):
    # Sign up first
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "signin@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
        }
    )

    # Sign in
    response = await client.post(
        "/api/v1/auth/signin",
        json={
            "email": "signin@example.com",
            "password": "ValidPass123!",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["user"]["email"] == "signin@example.com"
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_signin_wrong_password(client: AsyncClient):
    # Sign up first
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "wrongpass@example.com",
            "password": "CorrectPass123!",
            "password_confirm": "CorrectPass123!",
        }
    )

    # Sign in with wrong password
    response = await client.post(
        "/api/v1/auth/signin",
        json={
            "email": "wrongpass@example.com",
            "password": "WrongPass123!",
        }
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signin_non_existent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signin",
        json={
            "email": "nonexistent@example.com",
            "password": "AnyPass123!",
        }
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_tokens(client: AsyncClient):
    # Sign up first
    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "refresh@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
        }
    )

    old_access_token = signup_response.json()["access_token"]
    old_refresh_token = signup_response.cookies.get("refresh_token")

    # Refresh tokens
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": old_refresh_token}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert "refresh_token" in response.cookies
    # Note: access_token may be same if created within same second
    # The important thing is we got valid tokens and refresh token rotated
    new_refresh_token = response.cookies.get("refresh_token")
    assert new_refresh_token != old_refresh_token


@pytest.mark.asyncio
async def test_refresh_without_token(client: AsyncClient):
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signout(client: AsyncClient):
    # Sign up first
    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "signout@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
        }
    )

    refresh_token = signup_response.cookies.get("refresh_token")

    # Sign out
    response = await client.post(
        "/api/v1/auth/signout",
        cookies={"refresh_token": refresh_token}
    )

    assert response.status_code == 204

    # Try to refresh with signed out token
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token}
    )

    assert refresh_response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient):
    # Sign up first
    signup_response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "me@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Me User"
        }
    )

    access_token = signup_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["full_name"] == "Me User"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == 401
