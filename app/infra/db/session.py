"""Database session adapter."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import Settings


def create_engine_for(settings: Settings) -> AsyncEngine:
    """Create the application database engine."""
    return create_async_engine(settings.database_url, echo=settings.debug)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a non-expiring session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one request-scoped database session."""
    async with factory() as session:
        yield session
        await session.commit()
