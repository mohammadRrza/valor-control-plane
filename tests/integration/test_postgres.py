import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_connectivity() -> None:
    url = os.environ.get("VALOR_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("VALOR_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            result = await connection.scalar(text("SELECT 1"))
            assert result == 1
    finally:
        await engine.dispose()
