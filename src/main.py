"""Main entry point for the Plans Vision API."""

import uvicorn

from src.api import create_app
from src.config import get_settings


def main() -> None:
    """Run the application."""
    settings = get_settings()

    uvicorn.run(
        "src.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.log_level == "DEBUG",
    )


if __name__ == "__main__":
    main()
