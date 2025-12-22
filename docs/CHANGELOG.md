# CHANGELOG

All notable changes to this project will be documented in this file.
Use semantic versioning: MAJOR.MINOR.PATCH

---

## 1.1.0 (Unreleased) - Phase 1.5 SaaS Hardening

### Added
- **Multi-tenant foundation**
  - API key authentication middleware (X-API-Key header)
  - Backwards compatibility with X-Owner-Id header
  - Tenant isolation in storage and queries
  - Per-tenant quotas (max projects, max pages per project, monthly limits)
- **Rate limiting**
  - Fixed window rate limiting (60 req/min default)
  - X-RateLimit-* headers on all responses
  - 429 Too Many Requests with Retry-After header
- **Idempotency**
  - Idempotency-Key header support for safe retries
  - 24-hour cache TTL for idempotent responses
  - X-Idempotency-Replayed header on cached responses
- **Observability**
  - X-Request-ID header for request tracing
  - Structured logging with tenant_id, request_id, duration_ms
  - Metrics logging for pages_processed, guides_generated, guides_rejected
- **Error taxonomy**
  - Comprehensive error codes in docs/ERRORS.md
  - All error responses include schema_version and error_code
  - Structured pipeline error schema for failed analyses
- **Schema versioning**
  - All responses include schema_version field (currently "1.0")
  - BaseResponse class for consistent response structure
- **Storage hardening**
  - Image dimension validation (max 10000px default)
  - Tenant-scoped storage paths
  - Path traversal protection
  - Cleanup policy for old project files
- **Test fixtures**
  - testdata/ folder with synthetic test images
  - consistent_set/ for regression tests
  - contradiction_set/ for rejection tests

### Changed
- Error responses now include schema_version and structured error_code
- Storage paths now include tenant_id for isolation
- FileStorageError now includes error_code attribute

### Fixed
- Path traversal protection in file storage get_image_path()

---

## 1.0.0 (2025-12-22) - Phase 1 Visual Guide

### Added
- Multi-agent pipeline for visual guide generation
  - Guide Builder: Analyzes page 1 to extract candidate rules
  - Guide Applier: Validates rules against subsequent pages (2-N)
  - Self-Validator: Classifies rule stability (STABLE/PARTIAL/UNSTABLE)
  - Guide Consolidator: Produces final validated guide
- Single-page flow (Option B): Returns provisional guide only
- Contradiction detection: Any contradicted rule → UNSTABLE
- Strict JSON output validation with Pydantic schemas
- All 5 test gates passing:
  1. Single-page provisional only
  2. Consistent pages produce stable guide
  3. Contradictions prevent stable guide
  4. Invalid model output fails loudly
  5. Schema enforcement on agent outputs
- Tenant isolation via X-Owner-Id header
- PNG-only image upload validation
- SQLite storage with async support
- Structured logging with structlog

### API Endpoints
- `POST /projects` - Create new project
- `GET /projects` - List projects
- `GET /projects/{id}` - Get project details
- `POST /projects/{id}/pages` - Upload page (PNG only)
- `GET /projects/{id}/pages` - List pages
- `POST /projects/{id}/analyze` - Start analysis pipeline
- `GET /projects/{id}/status` - Get pipeline status
- `GET /projects/{id}/guide` - Get visual guide
- `GET /health` - Health check
