import uuid
from datetime import timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import User
from app.security import create_access_token
from tests.helpers import login, register

# --- Registration -----------------------------------------------------------


async def test_register_returns_user_without_password(client: AsyncClient) -> None:
    body = await register(client)

    assert body["email"] == "guest@example.com"
    assert body["full_name"] == "Test Guest"
    assert body["role"] == "guest"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_password_is_stored_hashed(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await register(client, password="correct-horse-battery")

    async with session_factory() as session:
        user = await session.scalar(select(User))

    assert user is not None
    assert user.hashed_password != "correct-horse-battery"
    assert user.hashed_password.startswith("$argon2")


async def test_register_rejects_duplicate_email_case_insensitively(client: AsyncClient) -> None:
    await register(client, email="guest@example.com")

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "GUEST@Example.com", "password": "another-password", "full_name": "Copy"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "long-enough-pw", "full_name": "A"},
        {"email": "a@example.com", "password": "short", "full_name": "A"},
        {"email": "a@example.com", "password": "long-enough-pw", "full_name": ""},
        {"email": "a@example.com", "full_name": "A"},
    ],
    ids=["bad-email", "short-password", "empty-name", "missing-password"],
)
async def test_register_validates_input(client: AsyncClient, payload: dict[str, str]) -> None:
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


# --- Login ------------------------------------------------------------------


async def test_login_returns_bearer_token(client: AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "guest@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_is_case_insensitive_on_email(client: AsyncClient) -> None:
    await register(client, email="guest@example.com")

    token = await login(client, email="Guest@Example.COM")

    assert token


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("guest@example.com", "wrong-password"),
        ("nobody@example.com", "correct-horse-battery"),
    ],
    ids=["wrong-password", "unknown-email"],
)
async def test_login_rejects_bad_credentials(
    client: AsyncClient, email: str, password: str
) -> None:
    await register(client)

    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )

    assert response.status_code == 401
    # Same message either way, so attackers can't tell which emails exist.
    assert response.json()["detail"] == "Incorrect email or password"


async def test_inactive_user_cannot_log_in(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await register(client)
    async with session_factory() as session:
        user = await session.scalar(select(User))
        assert user is not None
        user.is_active = False
        await session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "guest@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 401


# --- Protected routes -------------------------------------------------------


async def test_me_returns_current_user(client: AsyncClient) -> None:
    created = await register(client)
    token = await login(client)

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        create_access_token(str(uuid.uuid4()), "guest"),  # valid token, user doesn't exist
    ],
    ids=["garbage", "unknown-user"],
)
async def test_me_rejects_invalid_tokens(client: AsyncClient, token: str) -> None:
    await register(client)

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_me_rejects_expired_token(client: AsyncClient) -> None:
    created = await register(client)
    expired = create_access_token(created["id"], "guest", expires_in=timedelta(seconds=-1))

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"}
    )

    assert response.status_code == 401


async def test_me_rejects_token_signed_with_another_key(client: AsyncClient) -> None:
    created = await register(client)
    forged = jwt.encode({"sub": created["id"], "exp": 9999999999}, "y" * 64, algorithm="HS256")

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {forged}"}
    )

    assert response.status_code == 401
