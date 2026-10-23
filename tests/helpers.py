"""Shared helpers for API tests."""

from httpx import AsyncClient


async def register(
    client: AsyncClient,
    email: str = "guest@example.com",
    password: str = "correct-horse-battery",
    full_name: str = "Test Guest",
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login(
    client: AsyncClient,
    email: str = "guest@example.com",
    password: str = "correct-horse-battery",
) -> str:
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
