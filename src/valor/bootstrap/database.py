"""SQLAlchemy resource construction and lifecycle."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from valor.bootstrap.settings import DatabaseSettings


@dataclass(frozen=True, slots=True)
class DatabaseResources:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    async def close(self) -> None:
        await self.engine.dispose()


def create_database_resources(settings: DatabaseSettings) -> DatabaseResources:
    engine = create_async_engine(
        str(settings.url),
        pool_pre_ping=True,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_seconds,
    )
    return DatabaseResources(
        engine=engine,
        sessions=async_sessionmaker(engine, expire_on_commit=False, autoflush=False),
    )
