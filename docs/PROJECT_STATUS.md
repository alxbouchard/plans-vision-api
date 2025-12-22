# Project Status — plans-vision-api

## Current Phase
**API v1 Ready** — Phase 1 and Phase 1.5 Complete

## Release Summary

| Version | Phase | Status | Tests |
|---------|-------|--------|-------|
| v1.0.0 | Phase 1 — Visual Guide Generation | COMPLETE | 38 |
| v1.1.0 | Phase 1.5 — SaaS Hardening | COMPLETE | 66 |

---

## Phase 1 — Visual Guide Generation (COMPLETE)

### What is DONE
- Multi-page visual guide pipeline implemented
- Strict JSON outputs enforced via Pydantic schemas
- Provisional-only behavior for single page projects
- Explicit rejection on contradictory conventions
- MCAF framework integrated (AGENTS.md + docs)
- All 5 test gates implemented and passing
- Real-world pipeline test completed successfully (5 pages, 80% stability)
- Usage tracking with real-time cost estimation
- Test UI (test-ui.html) with progress visualization

### Test Gates (All Passing)
| Gate | Description | Test |
|------|-------------|------|
| Gate 1 | Single page → provisional_only | `TestSinglePageFlow` |
| Gate 2 | Consistent pages → stable guide | `TestConsistentPagesFlow` |
| Gate 3 | Contradiction → guide rejected | `TestContradictionFlow` |
| Gate 4 | Invalid model output → fail loudly | `TestInvalidModelOutput` |
| Gate 5 | Schema violation → validation error | `TestSchemaEnforcement` |

---

## Phase 1.5 — SaaS Hardening (COMPLETE)

### What is DONE
- **Multi-tenant foundation**
  - API key authentication (X-API-Key header)
  - Backwards compatibility with X-Owner-Id header
  - Tenant isolation in storage and queries
  - Per-tenant quotas (projects, pages, monthly limits)
- **Rate limiting**
  - Fixed window (60 req/min default)
  - X-RateLimit-* response headers
  - 429 Too Many Requests with Retry-After
- **Idempotency**
  - Idempotency-Key header support
  - 24-hour cache TTL
  - X-Idempotency-Replayed on cache hits
- **Observability**
  - X-Request-ID for request tracing
  - Structured logging (tenant_id, request_id, duration_ms)
  - Metrics logging (pages_processed, guides_generated, guides_rejected)
- **Error taxonomy**
  - Comprehensive error codes (docs/ERRORS.md)
  - All responses include schema_version and error_code
  - PipelineErrorSchema for structured step errors
- **Schema versioning**
  - All responses include `schema_version: "1.0"`
  - BaseResponse class for consistent structure
- **Storage hardening**
  - Image dimension validation (max 10000px)
  - Tenant-scoped storage paths
  - Path traversal protection
  - Cleanup policy for old files
- **Test fixtures**
  - testdata/ folder with consistent_set, contradiction_set, synthetic
  - generate_fixtures.py for reproducible images

---

## What is NOT STARTED (Do NOT implement yet)

Phase 2+ features require explicit user approval:

- Object extraction (rooms, doors, etc.)
- Bounding boxes or polygons
- PDF annotation output
- Viewer integration
- Pricing or SaaS billing
- Production deployment (Docker, CI/CD)

---

## Lock Dates
- Phase 1: 2024-12-22
- Phase 1.5: 2024-12-22

## Instruction for AI Agents

**Phases 1 and 1.5 are LOCKED.** Before any work:
1. Read AGENTS.md
2. Read docs/FEATURE_BuildGuide.md
3. Read docs/TEST_GATES.md
4. Read this file (PROJECT_STATUS.md)

**Any Phase 2 work requires explicit user approval and a new feature document.**
