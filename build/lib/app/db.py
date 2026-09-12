import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DEFAULT_DATABASE_URL = "postgresql+psycopg://procart:procart@localhost:5432/procart"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine() -> Engine:
    return create_engine(get_database_url(), future=True)
