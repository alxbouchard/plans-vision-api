"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.logging import configure_logging, get_logger
from src.storage import init_database
from src.api.routes import projects_router, pages_router, analysis_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    configure_logging()
    logger.info("application_startup", message="Starting Plans Vision API")

    await init_database()
    logger.info("database_initialized", message="Database initialized")

    yield

    # Shutdown
    logger.info("application_shutdown", message="Shutting down Plans Vision API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Plans Vision API",
        description=(
            "API for understanding construction plan conventions. "
            "Analyzes multiple pages of a project to learn visual conventions "
            "and produce a stable, reusable visual guide."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(projects_router)
    app.include_router(pages_router)
    app.include_router(analysis_router)

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle validation errors with structured response."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected errors."""
        logger.error(
            "unhandled_exception",
            error=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            },
        )

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "version": "1.0.0"}

    return app
