import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base


def pytest_addoption(parser):
    parser.addoption(
        "--require-postgres", action="store_true", help="Fail if PostgreSQL is unavailable"
    )


def pytest_configure(config):
    if config.getoption("--require-postgres") and not os.environ.get("TEST_DATABASE_URL"):
        raise pytest.UsageError("TEST_DATABASE_URL is mandatory for this integration gate")


@pytest.fixture(scope="session")
def database_url():
    """Create a new disposable database; never drop/truncate the supplied database."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL integration tests")
    parsed = make_url(url)
    assert parsed.drivername == "postgresql+psycopg"
    name = f"modelmedic_test_{uuid4().hex}"
    admin = create_engine(parsed, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    test_url = parsed.set(database=name).render_as_string(hide_password=False)
    previous = os.environ.get("MM_DATABASE_URL")
    os.environ["MM_DATABASE_URL"] = test_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
        yield test_url
    finally:
        if previous is None:
            os.environ.pop("MM_DATABASE_URL", None)
        else:
            os.environ["MM_DATABASE_URL"] = previous
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def db(database_url):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield engine, sessionmaker(engine, expire_on_commit=False)
    engine.dispose()
