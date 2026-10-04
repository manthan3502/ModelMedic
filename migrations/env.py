from alembic import context

from backend.app.core.config import Settings
from backend.app.db.models import Base
from backend.app.db.session import create_db

settings = Settings()  # type: ignore[call-arg]

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine, _ = create_db(settings)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
