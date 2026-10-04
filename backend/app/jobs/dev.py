"""Internal local-only queue command. No dummy-job creation HTTP route."""

import argparse
from uuid import UUID, uuid4

from backend.app.core.config import Settings
from backend.app.db.session import check_schema, create_db
from backend.app.domain.jobs import DuplicateActiveJob
from backend.app.services.queue import Queue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=UUID, default=None)
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args()
    settings = Settings()  # type: ignore[call-arg]
    if settings.environment != "local" or settings.deployment_mode == "demo":
        parser.error("The dummy-job command is local full-mode only")
    engine, sessions = create_db(settings)
    try:
        check_schema(engine)
        try:
            job = Queue(sessions).enqueue(
                "M0_DUMMY", "INTERNAL", args.target or uuid4(), {"fail": args.fail}
            )
        except DuplicateActiveJob:
            parser.exit(2, "Duplicate active job rejected.\n")
        print(job.id)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
