# Project Status — plans-vision-api

## Current Phase
**API v3 Ready** — Phase 1, Phase 1.5, Phase 2, and Phase 3 Complete

## Release Summary

| Version | Phase | Status |
|---------|-------|--------|
| v1.0.0 | Phase 1 — Visual Guide Generation | COMPLETE |
| v1.1.0 | Phase 1.5 — SaaS Hardening | COMPLETE |
| v2.0.0 | Phase 2 — Extraction and Query | COMPLETE |
| v3.0.0 | Phase 3 — Render | COMPLETE |

### Test Gate

Run `./scripts/test_summary.sh` to verify test counts. Do not hardcode.

**Last verified:** Run script for current counts.

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
  - **Bugfix (df8f5eb)**: PageClassifier never returns UNKNOWN for readable pages
    - Fallback to DETAIL with confidence=0.2 on errors
    - Express uncertainty via confidence, not via UNKNOWN type
    - 11 regression tests added

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

## Phase 3 — Render (COMPLETE)

### Goal
Anchor extracted objects to the master PDF and provide annotated output.
Renderer performs zero model calls. All geometry derived from mapping.

### What is DONE
- **V3 schemas** (schemas_v3.py)
  - PDFUploadResponse, MappingResponse, PageMapping
  - AffineTransform for PNG→PDF coordinate conversion
  - GeometryPNG (bbox) and GeometryPDF (rect)
  - TraceInfo for reproducibility
  - RenderPDFRequest, RenderAnnotationsRequest
  - ErrorResponseV3 with PDF_MISMATCH, MAPPING_REQUIRED
- **V3 endpoints** (routes_v3.py)
  - POST /v3/projects/{project_id}/pdf — Upload PDF master
  - POST /v3/projects/{project_id}/pdf/{pdf_id}/build-mapping — Start mapping job
  - GET /v3/projects/{project_id}/pdf/{pdf_id}/mapping/status — Mapping status
  - GET /v3/projects/{project_id}/pdf/{pdf_id}/mapping — Get mapping data
  - POST /v3/projects/{project_id}/render/pdf — Render annotated PDF
  - GET /v3/projects/{project_id}/render/pdf/{render_job_id} — Render status
  - POST /v3/projects/{project_id}/render/annotations — Export annotations
- **Database tables** (database.py)
  - PDFMasterTable, MappingJobTable, PageMappingTable, RenderJobTable
- **Coordinate transform**
  - Affine matrix [a, b, c, d, e, f] for scaling/translation
  - Rotation support (0, 90, 180, 270 degrees)
  - Cropbox/mediabox offset handling
- **Test coverage**
  - 25 schema validation tests (test_render.py)
  - 14 endpoint tests (test_v3_endpoints.py)
  - All gates tested: fingerprint mismatch, mapping required, pure render

### Test Gates (All Passing)
| Gate | Description | Test |
|------|-------------|------|
| Gate 1 | Fingerprint mismatch → PDF_MISMATCH | `TestGate1_FingerprintMismatch` |
| Gate 2 | Mapping missing → MAPPING_REQUIRED | `TestGate2_MappingRequired` |
| Gate 3 | Coordinate transform correctness | `TestGate3_CoordinateTransform` |
| Gate 4 | Rotation coverage (0, 90, 180, 270) | `TestGate4_RotationCoverage` |
| Gate 5 | Cropbox coverage | `TestGate5_CropboxCoverage` |
| Gate 6 | Renderer is pure (zero model calls) | `TestGate6_RendererPure` |
| Gate 7 | PDF output contains annotations | `TestGate7_PDFAnnotations` |
| Gate 8 | Annotated PDF is reproducible | `TestGate8_Reproducibility` |

---

## What is NOT STARTED (Do NOT implement yet)

Phase 4+ features require explicit user approval:

- Polygon geometry (Phase 3.1)
- XFDF export
- Viewer integration
- Pricing or SaaS billing
- Production deployment (Docker, CI/CD)

---

## Lock Dates
- Phase 1: 2024-12-22
- Phase 1.5: 2024-12-22
- Phase 2: 2025-12-22
- Phase 3: 2025-12-23

## Instruction for AI Agents

**Phases 1, 1.5, 2, and 3 are LOCKED.** Before any work:
1. Read AGENTS.md
2. Read docs/FEATURE_Render_MasterPDF.md
3. Read docs/TEST_GATES_RENDER.md
4. Read this file (PROJECT_STATUS.md)


## Phase 3.2 — Provisional Mode (ACTIVE WHEN STABLE GUIDE IS REJECTED)

This is not a new development phase. It is a runtime operating mode.

Trigger condition:
- Analyze completes with: has_provisional=true AND has_stable=false
- And stable guide is rejected due to insufficient stable_ratio

Expected status behavior:
- Do NOT mark the project as "failed".
- Mark the project as "provisional_only" (stable rejected, provisional available).
- Provide rejection_reason for the stable guide.

What is allowed in provisional_only:
- Phase 2 extraction is allowed using the provisional guide (conservative policy).
- Query and render are allowed, but results must clearly indicate guide_source="provisional".

Constraints:
- No hardcoded semantics.
- No arbitrary disambiguation (return ambiguous=true when needed).
- No low-confidence extraction in provisional_only.

Purpose:
Support small addenda sets (e.g., 2–5 pages) that are usable for locating specific elements even when cross-page conventions are not stable enough to produce a stable guide.



**Any Phase 4 work requires explicit user approval and a new feature document.**
