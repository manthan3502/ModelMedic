from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import Settings

SCHEMA_REVISION = "0001_m0"


def create_db(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
    return engine, sessionmaker(engine, expire_on_commit=False)


def check_schema(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        versions = (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        )
        if versions != [SCHEMA_REVISION]:
            raise RuntimeError("Unsupported database schema; run the explicit migration step")
