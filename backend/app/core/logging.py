import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Only reviewed messages/identifiers; never serialize exceptions, params or request bodies.
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                "request_id": getattr(record, "request_id", None),
                "job_id": getattr(record, "job_id", None),
            }
        )


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("modelmedic")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
