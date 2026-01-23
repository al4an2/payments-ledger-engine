import os
import uuid

import pytest
import pytest_asyncio
from typing import cast
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from payments_ledger.data_models.db_models import Base


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    return cast(str, url)


@pytest_asyncio.fixture(scope="session")
async def async_engine(test_db_url: str):
    schema = f"test_{uuid.uuid4().hex}"
    engine = create_async_engine(
        test_db_url,
        connect_args={"server_settings": {"search_path": schema}},
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    SessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE idempotency_keys, ledger_entries, accounts, clients "
                "RESTART IDENTITY CASCADE"
            )
        )
