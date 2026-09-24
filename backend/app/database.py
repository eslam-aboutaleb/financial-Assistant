import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Use centralized settings; defaults to aiosqlite in app/data when DATABASE_URL is not set.
DATABASE_URL = settings.database_url

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_all_tables():
    from app.models.base import Base
    # import models to register them
    import app.models.user  # noqa
    import app.models.claim  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
