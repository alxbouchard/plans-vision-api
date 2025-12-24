# Project Status — plans-vision-api

## Current Phase
**API v3 Ready** — Phase 1, Phase 1.5, Phase 2, and Phase 3 Complete
**Phase 3.2 — Provisional Mode available (runtime mode)**
**Phase 3.3 — Spatial Room Labeling: Gate 1 complete**

## Release Summary

| Version | Phase | Status |
|--------|-------|--------|
| v1.0.0 | Phase 1 — Visual Guide Generation | COMPLETE |
| v1.1.0 | Phase 1.5 — SaaS Hardening | COMPLETE |
| v2.0.0 | Phase 2 — Extraction and Query | COMPLETE |
| v3.0.0 | Phase 3 — Render | COMPLETE |
| v3.2.0 | Phase 3.2 — Provisional Mode | ACTIVE (runtime mode) |

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
- Real-world pipeline test completed successfully (5 pages, ≥80% stability)
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
- API key authentication (X-API-Key)
- Tenant isolation and quotas
- Rate limiting with Retry-After
- Idempotency support
- Structured logging and observability
- Error taxonomy (docs/ERRORS.md)
- Schema versioning
- Storage hardening and cleanup
- Reproducible test fixtures

---

## Phase 2 — Extraction and Query (COMPLETE)

### What is DONE
- Page classification with vision model
- **Bugfix (df8f5eb): classifier never returns UNKNOWN for readable pages**
  - Fallback to DETAIL with confidence=0.2
  - Uncertainty expressed via confidence, not type
  - 11 regression tests
- **Bugfix (Phase 3.2): page classification persisted to database**
  - PageTable now has `page_type`, `classification_confidence`, `classified_at` columns
  - Overlay reads `page_type` from database (single source of truth)
  - No in-memory-only storage for data the API must serve
  - **Schema change**: requires `rm plans_vision.db` before restart
- Extraction pipeline (rooms, doors, schedules)
- Deterministic indexing
- Explicit ambiguity handling
- Strict schema enforcement
- All Phase 2 test gates passing

---

## Phase 3 — Render (COMPLETE)

### Goal
Anchor extracted objects to the master PDF using deterministic geometry.

### What is DONE
- V3 schemas and endpoints
- PDF-first mapping pipeline
- Affine transforms with rotation + cropbox support
- Renderer is pure (zero model calls)
- Annotated PDF output
- Full test coverage for render gates

---

## Phase 3.2 — Provisional Mode (RUNTIME MODE) — IMPLEMENTED

**This is NOT a new development phase.**
It is a **runtime operating mode** activated when a stable guide cannot be generated.

### Implementation (commit df8f5eb+)
- Added `ProjectStatus.PROVISIONAL_ONLY` enum value
- Orchestrator uses `PROVISIONAL_ONLY` instead of `FAILED` when provisional guide exists
- `PipelineStatusResponse` includes `has_provisional`, `has_stable`, `rejection_reason`
- UI displays "Provisional mode" and enables extraction

### Trigger Condition
- Analyze completes with:
  - `has_provisional = true`
  - `has_stable = false`
- Stable guide rejected due to insufficient stability ratio

### Required Behavior ✅
- Project MUST NOT be marked as `failed` ✅
- Project MUST be marked as `provisional_only` ✅
- `rejection_reason` MUST be preserved and returned ✅

### What is Allowed in `provisional_only`
- Phase 2 extraction using the provisional guide ✅
- Query endpoints remain available ✅
- Render endpoints remain available ✅
- All results include `guide_source="provisional"` and `extraction_policy="relaxed"` ✅

### RELAXED Extraction Policy (provisional_only mode)
- `ExtractionPolicy.RELAXED` activated when `has_provisional=true && has_stable=false`
- Room extraction: allow LOW confidence only if room_number is 2-4 digit token
- Door extraction: allow LOW confidence only if door_number is explicitly provided (no arc-only)
- All results carry `extraction_policy:relaxed` and `guide_source:provisional` in sources
- CONSERVATIVE policy unchanged for stable guide mode
- 10 regression tests added (`TestPhase32_RelaxedExtractionPolicy`)

### Constraints (Non-Negotiable)
- No hardcoded semantics
- No arbitrary disambiguation
- Ambiguity MUST be explicit (`ambiguous=true`)
- RELAXED policy only lowers threshold for explicitly labeled objects
- Never invent, never disambiguate arbitrarily

### Purpose
Support **small plan sets and addenda (2–5 pages)** that are:
- insufficiently stable for a global visual guide
- but **fully usable for locating specific elements**

This mode ensures the API:
- understands the plan
- extracts verifiable elements
- remains honest about uncertainty
- does NOT over-claim understanding

---

## What is NOT STARTED (Do NOT implement)

- Phase 4 features
- Polygon geometry
- XFDF export
- Viewer integration
- Pricing or billing
- Production deployment

---

## Lock Dates
- Phase 1: 2024-12-22
- Phase 1.5: 2024-12-22
- Phase 2: 2025-12-22
- Phase 3: 2025-12-23

---

## Instructions for AI Agents

**Phases 1, 1.5, 2, 3 are LOCKED.**

Before any work:
1. Read `AGENTS.md`
2. Read `docs/PROJECT_STATUS.md`
3. Read `docs/SESSION_PLAYBOOK.md`
4. Read relevant TEST_GATES docs

**Any Phase 4 work requires explicit user approval and a new feature document.**