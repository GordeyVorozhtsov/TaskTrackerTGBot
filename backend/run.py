#!/usr/bin/env python3
"""Run the TG Task Tracker server."""

import uvicorn

from app.core.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        timeout_graceful_shutdown=10,
    )


if __name__ == "__main__":
    main()
