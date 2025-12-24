# Project Status — plans-vision-api

## Current Phase
**API v3 Ready** — Phase 1, Phase 1.5, Phase 2, and Phase 3 are COMPLETE.  
**Phase 3.2 — Provisional Mode** is ACTIVE at runtime when a stable visual guide cannot be generated.

---

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
- Provisional-only behavior for single-page projects
- Explicit rejection on contradictory conventions
- MCAF framework integrated (AGENTS.md + docs)
- All test gates implemented and passing
- Real-world pipeline test completed successfully (5 pages, ≥80% stability)
- Usage tracking with real-time cost estimation
- Test UI (`test-ui.html`) with progress visualization

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
  - Backward compatibility with X-Owner-Id
  - Tenant isolation in storage and queries
  - Per-tenant quotas (projects, pages, monthly limits)
- **Rate limiting**
  - Fixed window (default 60 req/min)
  - X-RateLimit-* headers
  - 429 responses with Retry-After
- **Idempotency**
  - Idempotency-Key support
  - 24h TTL cache
  - X-Idempotency-Replayed header
- **Observability**
  - X-Request-ID propagation
  - Structured logging (tenant_id, request_id, duration_ms)
  - Metrics logging (pages_processed, guides_generated, guides_rejected)
- **Error taxonomy**
  - Centralized error codes (docs/ERRORS.md)
  - Structured PipelineErrorSchema
- **Schema versioning**
  - All responses include schema_version
- **Storage hardening**
  - Image dimension validation
  - Tenant-scoped paths
  - Path traversal protection
  - Cleanup policy
- **Test fixtures**
  - Reproducible datasets (consistent, contradiction, synthetic)

---

## Phase 2 — Extraction and Query (COMPLETE)

### What is DONE
- **Image metadata storage**
  - width, height, sha256, byte_size stored on upload
  - Overlay endpoint returns real dimensions
- **Page classification**
  - PageType enum: plan, schedule, notes, legend, detail, unknown
  - Vision-based PageClassifier
  - Classification persisted per page
  - PageClassifier never returns UNKNOWN for readable pages
  - Uncertainty expressed via confidence, not type
- **Extraction pipeline**
  - Async extract job
  - Steps: classify_pages → extract_objects → build_index
- **Room extraction**
  - Conservative policy: room_number required
  - Bounding box geometry only
- **Door extraction**
  - Plan-only extraction
  - Conservative DoorType enum
- **Schedule extraction**
  - Table-only parsing
  - Isolated from plan logic
- **Project index**
  - Deterministic hashing
  - Coordinate bucketing
  - rooms_by_number, objects_by_type maps
- **Query endpoint**
  - Explicit ambiguity handling
  - Never auto-select on conflict
- **Schema enforcement**
  - Strict Pydantic validation
  - Invalid outputs fail loudly

### Test Gates (All Passing)
| Gate | Description | Test |
|------|-------------|------|
| Gate A | Page classification required | `TestGateA_PageClassification` |
| Gate B | Rooms extracted | `TestGateB_RoomsExtraction` |
| Gate C | Query by room number | `TestGateCD_Query` |
| Gate D | Ambiguity explicit | `TestGateCD_Query` |
| Gate E | Doors extracted conservatively | `TestGateE_DoorsExtraction` |
| Gate F | Schedule isolation | ScheduleExtractor |
| Gate G | Schema enforcement | `TestGateG_SchemaEnforcement` |
| Gate H | Deterministic index | `TestGateH_DeterministicIndex` |

---

## Phase 3 — Render (COMPLETE)

### Goal
Anchor extracted objects to the master PDF using deterministic geometry.  
Renderer performs **zero model calls**.

### What is DONE
- V3 schemas for mapping, transforms, rendering
- PDF upload and fingerprinting
- Mapping job with affine transforms
- Full rotation and cropbox support
- Deterministic render jobs
- Annotated PDF output
- Annotation export endpoint

### Test Gates (All Passing)
| Gate | Description | Test |
|------|-------------|------|
| Gate 1 | Fingerprint mismatch | `TestGate1_FingerprintMismatch` |
| Gate 2 | Mapping required | `TestGate2_MappingRequired` |
| Gate 3 | Transform correctness | `TestGate3_CoordinateTransform` |
| Gate 4 | Rotation coverage | `TestGate4_RotationCoverage` |
| Gate 5 | Cropbox coverage | `TestGate5_CropboxCoverage` |
| Gate 6 | Renderer purity | `TestGate6_RendererPure` |
| Gate 7 | PDF annotations present | `TestGate7_PDFAnnotations` |
| Gate 8 | Reproducibility | `TestGate8_Reproducibility` |

---

## Phase 3.2 — Provisional Mode (RUNTIME MODE)

**This is not a new development phase.**  
It is a runtime operating mode used when a stable guide cannot be generated.

### Trigger Condition
- Analyze completes with:
  - has_provisional = true
  - has_stable = false
- Stable guide rejected due to insufficient stability ratio

### Expected Behavior
- Project MUST NOT be marked as failed
- Project is marked as `provisional_only`
- Stable guide rejection reason is preserved and returned

### What is Allowed
- Phase 2 extraction using the provisional guide
- Query endpoints remain available
- Render endpoints remain available
- All results must declare `guide_source = provisional`

### Constraints
- No hardcoded semantics
- No arbitrary disambiguation
- Ambiguity must be explicit
- No low-confidence extraction

### Purpose
Support small or partial document sets (e.g. addendas, 2–5 pages) that are sufficient for locating specific elements even when cross-page conventions are not stable enough to produce a fully stable guide.

---

## What is NOT STARTED (Do NOT implement)

- Phase 4 features
- Polygon geometry
- XFDF export
- Viewer integration
- Billing or pricing
- Production deployment

---

## Lock Dates
- Phase 1: 2024-12-22
- Phase 1.5: 2024-12-22
- Phase 2: 2025-12-22
- Phase 3: 2025-12-23

---

## Instruction for AI Agents

**Phases 1, 1.5, 2, and 3 are LOCKED.**

Before any work:
1. Read AGENTS.md
2. Read this file (PROJECT_STATUS.md)
3. Read relevant TEST_GATES and FEATURE documents

**Any Phase 4 work requires explicit user approval and a new feature document.**