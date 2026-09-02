from unittest.mock import AsyncMock, MagicMock

import pytest

from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_uow_does_not_commit_implicitly() -> None:
    session = AsyncMock()
    factory = MagicMock(return_value=session)
    async with SqlAlchemyUnitOfWork(factory):
        pass
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_uow_rolls_back_on_exception() -> None:
    session = AsyncMock()
    factory = MagicMock(return_value=session)
    with pytest.raises(ValueError, match="abort"):
        async with SqlAlchemyUnitOfWork(factory):
            raise ValueError("abort")
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_uow_explicit_commit_and_rollback() -> None:
    session = AsyncMock()
    uow = SqlAlchemyUnitOfWork(MagicMock(return_value=session))
    async with uow:
        await uow.commit()
        await uow.rollback()
    session.commit.assert_awaited_once()
    assert session.rollback.await_count == 2


@pytest.mark.asyncio
async def test_uow_rejects_operations_before_enter() -> None:
    uow = SqlAlchemyUnitOfWork(MagicMock())
    with pytest.raises(RuntimeError, match="has not been entered"):
        await uow.commit()
    with pytest.raises(RuntimeError, match="has not been entered"):
        await uow.rollback()


@pytest.mark.asyncio
async def test_uow_closes_session_when_automatic_rollback_fails() -> None:
    session = AsyncMock()
    session.rollback.side_effect = RuntimeError("rollback failed")
    with pytest.raises(RuntimeError, match="rollback failed"):
        async with SqlAlchemyUnitOfWork(MagicMock(return_value=session)):
            pass
    session.close.assert_awaited_once()
