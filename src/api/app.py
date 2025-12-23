"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.logging import configure_logging, get_logger
from src.storage import init_database
from src.api.routes import projects_router, pages_router, analysis_router
from src.api.routes_v2 import extraction_router, query_router
from src.api.routes_v3 import router as v3_router
from src.api.middleware import (
    APIKeyAuthMiddleware,
    RateLimitMiddleware,
    IdempotencyMiddleware,
    RequestContextMiddleware,
)
from src.api.middleware.auth import register_tenant
from src.models.schemas import SCHEMA_VERSION

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    configure_logging()
    logger.info("application_startup", message="Starting Plans Vision API")

    await init_database()
    logger.info("database_initialized", message="Database initialized")

    # Optionally register a demo API key for local testing
    # Set PLANS_VISION_DEMO_KEY env var to enable
    import os
    demo_key = os.environ.get("PLANS_VISION_DEMO_KEY")
    if demo_key:
        from src.api.middleware.auth import hash_api_key, _tenant_store
        from uuid import UUID
        from datetime import datetime

        demo_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        key_hash = hash_api_key(demo_key)
        _tenant_store[key_hash] = {
            "tenant_id": demo_tenant_id,
            "name": "demo",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "projects_count": 0,
            "pages_this_month": 0,
            "usage_reset_at": datetime.utcnow(),
        }
        logger.info("demo_key_created", message="Demo API key registered from PLANS_VISION_DEMO_KEY")
        print(f"\n{'='*60}")
        print(f"DEMO API KEY: {demo_key}")
        print(f"{'='*60}\n")

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

    # Middleware stack (order matters - last added = first executed)
    # So we add in reverse order of desired execution:
    # Execution order: CORS -> Auth -> RateLimit -> RequestContext -> Idempotency

    # 5. Idempotency - caches responses for retry safety (needs tenant_id)
    app.add_middleware(IdempotencyMiddleware)

    # 4. Request context - adds request_id and timing (needs tenant_id from auth)
    app.add_middleware(RequestContextMiddleware)

    # 3. Rate limiting - must run after auth (so it has tenant_id)
    app.add_middleware(RateLimitMiddleware)

    # 2. Authentication - extracts tenant_id from API key
    app.add_middleware(APIKeyAuthMiddleware)

    # 1. CORS - must execute first to handle preflight and add headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(projects_router)
    app.include_router(pages_router)
    app.include_router(analysis_router)

    # V2 routers (extraction and query)
    app.include_router(extraction_router)
    app.include_router(query_router)

    # V3 routers (PDF master, mapping, render)
    app.include_router(v3_router)

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
                "schema_version": SCHEMA_VERSION,
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
                "schema_version": SCHEMA_VERSION,
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


# Create application instance for uvicorn
app = create_app()
