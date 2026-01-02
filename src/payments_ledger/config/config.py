from os import getenv
from dotenv import load_dotenv

load_dotenv()

def _get_db_params() -> str:
    user = getenv("POSTGRES_USER", "postgres")
    password = getenv("POSTGRES_PASSWORD", "postgres")
    host = getenv("POSTGRES_HOST", "localhost")
    port = getenv("POSTGRES_PORT", "5432")
    db = getenv("POSTGRES_DB", "postgres")
    return user, password, host, port, db

def get_sync_db_url() -> str:
    user, password, host, port, db = _get_db_params()
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

def get_async_db_url() -> str:
    user, password, host, port, db = _get_db_params()
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

