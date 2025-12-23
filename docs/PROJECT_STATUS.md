# Project Status — plans-vision-api

## Current Phase
**API v2 Ready** — Phase 1, Phase 1.5, and Phase 2 Complete

## Release Summary

| Version | Phase | Status | Tests |
|---------|-------|--------|-------|
| v1.0.0 | Phase 1 — Visual Guide Generation | COMPLETE | 38 |
| v1.1.0 | Phase 1.5 — SaaS Hardening | COMPLETE | 66 |
| v2.0.0 | Phase 2 — Extraction and Query | COMPLETE | 98 |

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

## Phase 2 — Extraction and Query (COMPLETE)

### What is DONE
- **Image metadata storage** (Phase 2 bugfix)
  - Store image_width, image_height, image_sha256, byte_size on upload
  - Overlay endpoint returns real dimensions instead of hardcoded 800x600
  - Lazy backfill for pages created before this feature
  - 8 new tests for metadata storage and retrieval

- **Page classification**
  - PageType enum: plan, schedule, notes, legend, detail, unknown
  - PageClassifier with vision model integration
  - Classification persistence and retrieval
  - Gate A tests passing

- **Extraction pipeline**
  - POST /v2/projects/{id}/extract endpoint
  - Async extraction job with status tracking
  - Steps: classify_pages, extract_objects, build_index
  - GET /v2/projects/{id}/extract/status endpoint

- **Room extraction**
  - RoomExtractor with vision model integration
  - Conservative rules: room_number required, no low confidence
  - Bbox geometry [x, y, w, h] format
  - Gates B and C tests passing

- **Door extraction**
  - DoorExtractor with vision model integration
  - DoorType enum: single, double, sliding, revolving, unknown
  - Only extracted from plan pages
  - Gate E tests passing

- **Schedule extraction**
  - ScheduleExtractor for table parsing
  - Isolated from plan extraction
  - Gate F tests passing

- **Project index**
  - Deterministic ID generation using stable hashing
  - Coordinate bucketing (50px) for stability
  - rooms_by_number and objects_by_type maps
  - Gate H tests passing

- **Query endpoint**
  - GET /v2/projects/{id}/query with room_number, room_name, type params
  - Ambiguity detection: multiple matches → ambiguous=true
  - Per PHASE2_DECISIONS.md: never pick arbitrarily
  - Gate D tests passing

- **Schema enforcement**
  - All v2 responses include schema_version: "2.0"
  - Pydantic validation for all extraction outputs
  - Invalid data fails loudly
  - Gate G tests passing

### Test Gates (All Passing)
| Gate | Description | Test |
|------|-------------|------|
| Gate A | Page classification required | `TestGateA_PageClassification` |
| Gate B | Rooms extracted on consistent_set | `TestGateB_RoomsExtraction` |
| Gate C | Query room number works | `TestGateCD_Query` |
| Gate D | Ambiguous query is explicit | `TestGateCD_Query` |
| Gate E | Doors extracted with conservative rules | `TestGateE_DoorsExtraction` |
| Gate F | Schedule parsing isolated | ScheduleExtractor |
| Gate G | Schema enforcement | `TestGateG_SchemaEnforcement` |
| Gate H | Deterministic index | `TestGateH_DeterministicIndex` |

---

## What is NOT STARTED (Do NOT implement yet)

Phase 3+ features require explicit user approval:

- Polygon geometry (Phase 2.1)
- PDF annotation output
- Viewer integration
- Pricing or SaaS billing
- Production deployment (Docker, CI/CD)

---

## Lock Dates
- Phase 1: 2024-12-22
- Phase 1.5: 2024-12-22
- Phase 2: 2025-12-22

## Instruction for AI Agents

**Phases 1, 1.5, and 2 are LOCKED.** Before any work:
1. Read AGENTS.md
2. Read docs/FEATURE_BuildGuide.md or docs/FEATURE_ExtractObjects.md
3. Read docs/TEST_GATES.md or docs/TEST_GATES_PHASE2.md
4. Read this file (PROJECT_STATUS.md)

**Any Phase 3 work requires explicit user approval and a new feature document.**
