from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models import User
from app.schemas import UserCreate
from app.security import DUMMY_HASH, hash_password, verify_password


class EmailAlreadyRegisteredError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == normalize_email(email)))


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    email = normalize_email(data.email)
    if await get_user_by_email(session, email) is not None:
        raise EmailAlreadyRegisteredError(email)

    # Argon2 is deliberately slow and CPU-bound; run it off the event loop.
    hashed = await run_in_threadpool(hash_password, data.password)
    user = User(email=email, full_name=data.full_name, hashed_password=hashed)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Two signups with the same email raced past the check above.
        await session.rollback()
        raise EmailAlreadyRegisteredError(email) from None
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if user is None:
        await run_in_threadpool(verify_password, password, DUMMY_HASH)
        return None
    if not await run_in_threadpool(verify_password, password, user.hashed_password):
        return None
    return user
