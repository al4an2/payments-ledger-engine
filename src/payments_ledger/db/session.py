from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from payments_ledger.config.config import get_async_db_url

DATABASE_URL = get_async_db_url()


def create_engine(db_url: str = DATABASE_URL) -> AsyncEngine:
    return create_async_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = create_engine(db_url=DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    async with SessionLocal() as session:
        yield session


def get_session_factory():
    return SessionLocal
