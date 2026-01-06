"""API routes."""

from .projects import router as projects_router
from .pages import router as pages_router
from .analysis import router as analysis_router
from .pdf import router as pdf_router

__all__ = ["projects_router", "pages_router", "analysis_router", "pdf_router"]
