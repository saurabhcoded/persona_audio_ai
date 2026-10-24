"""Run the API server: `uv run main.py` (add `--reload` / `--no-reload` to override the default).

Host, port and workers come from Settings (.env / environment). Auto-reload is on by default
only when ENVIRONMENT=local.
"""

import argparse

import uvicorn

from app.core.config import settings
from app.core.logging import setup_logging


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=f"Run {settings.app_name}")
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=settings.environment == "local",
        help="restart on code changes (default: on when ENVIRONMENT=local)",
    )
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        reload_dirs=["app"] if args.reload else None,
        workers=None if args.reload else settings.workers,
        proxy_headers=True,
        log_config=None,  # keep app.core.logging's format
    )


if __name__ == "__main__":
    main()
