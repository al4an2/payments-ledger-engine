from os import getenv
from dotenv import load_dotenv

load_dotenv()

def get_sync_db_url() -> str:
    user = getenv("POSTGRES_USER", "postgres")
    password = getenv("POSTGRES_PASSWORD", "postgres")
    host = getenv("POSTGRES_HOST", "localhost")
    port = getenv("POSTGERS_PORT", "5432")
    db = getenv("POSTGRES_DB", "postgres")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
