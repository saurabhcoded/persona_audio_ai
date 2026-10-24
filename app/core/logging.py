import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # The reloader logs every file change at DEBUG; keep it quiet even with LOG_LEVEL=DEBUG.
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
