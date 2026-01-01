from os import getenv
from alembic import context

config = context.config

def get_url() -> str:
    user = getenv("POSTGRES_USER", "postgres")
    password = getenv("POSTGRES_PASSWORD", "postgres")
    host = getenv("POSTGRES_HOST", "localhost")
    port = getenv("POSTGERS_PORT", "5432")
    db = getenv("POSTGRES_DB", "postgres")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

config.set_main_option("sqlalchemy.url", get_url())
