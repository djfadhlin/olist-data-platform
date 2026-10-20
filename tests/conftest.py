
"""Shared pytest configuration for Olist Data Platform."""

import os
import sys
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(dotenv_path=ROOT / ".env")


@pytest.fixture(scope="session")
def db():
    """Provide a PostgreSQL connection for integration tests."""

    connection = psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        autocommit=True,
    )

    try:
        yield connection
    finally:
        connection.close()


def q1(db, sql):
    """Return the first column of the first SQL result row."""

    with db.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]
