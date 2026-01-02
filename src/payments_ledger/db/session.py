from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.payments_ledger.config.config import get_async_db_url

DATABASE_URL = get_async_db_url()

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session():
    async with SessionLocal() as session:
        yield session