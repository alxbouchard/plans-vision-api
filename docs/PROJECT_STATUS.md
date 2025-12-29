# Project Status — plans-vision-api

## Current Phase
**API v3 Ready** — Phase 1, Phase 1.5, Phase 2, and Phase 3 Complete
**Phase 3.2 — Provisional Mode available (runtime mode)**
**Phase 3.3 — Spatial Room Labeling: VALIDATED & FROZEN**
**Phase 3.4 — Single Page Room Extraction: IN PROGRESS**

## Release Summary

| Version | Phase | Status |
|--------|-------|--------|
| v1.0.0 | Phase 1 — Visual Guide Generation | COMPLETE |
| v1.1.0 | Phase 1.5 — SaaS Hardening | COMPLETE |
| v2.0.0 | Phase 2 — Extraction and Query | COMPLETE |
| v3.0.0 | Phase 3 — Render | COMPLETE |
| v3.2.0 | Phase 3.2 — Provisional Mode | ACTIVE (runtime mode) |
| v3.3.0 | Phase 3.3 — Spatial Room Labeling | FROZEN |
| v3.4.0 | Phase 3.4 — Single Page Extraction | IN PROGRESS |

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

## Phase 3.3 — Spatial Room Labeling (FROZEN)

### Status: VALIDATED & FROZEN

Phase 3.3 is complete and frozen per Decision 6/7/8 in `docs/DECISIONS_Phase3_3.md`.

### What is DONE
- SpatialRoomLabeler driven by Visual Guide payloads
- 3 mandatory payloads: token_detector(room_name), token_detector(room_number), pairing
- Test gates A/B/C passing
- Feature flag `ENABLE_PHASE3_3_SPATIAL_LABELING`

### Frozen Components (DO NOT MODIFY)
- `src/extraction/spatial_room_labeler.py`
- `tests/test_phase3_3_gates.py`
- Phase 3.3 payload schema

---

## Phase 3.4 — Single Page Room Extraction (IN PROGRESS)

### Goal
Make the API capable of extracting rooms from a SINGLE page reliably, without requiring multi-page validation.

### What is DONE
- [x] Ticket 1: GuideBuilder prompt updated for single-page observations
- [x] Ticket 2: GuideApplier payload_validations schema added
- [x] Ticket 3: GuideConsolidator single-page rules
- [x] Ticket 4: Test gates A/B/C created (24 tests passing)
- [x] Ticket 5: DPI robustness tests
- [x] Phase 0: TokenProvider unified interface (PyMuPDF + Vision + OCR)
- [x] Phase 0: PyMuPDFTokenProvider extracts text from PDF vector layer
- [x] Phase 0: TokenBlockAdapter pairs room_name + room_number by proximity
- [x] Gate validated: addenda_page_1 rooms_emitted = 296 (via PDF direct)
- [x] Gate validated: test2_page6 rooms_emitted = 510 (via PDF direct)

### Phase 3.5 — Tokens-First Extraction (VALIDATED)

**Status: VALIDATED** - Le moteur d'extraction tokens-first fonctionne.

Le problème restant est 100% sémantique (faux positifs) et relève du Visual Guide, pas du code.

| Fixture | Tokens | Rooms Baseline | Observation |
|---------|--------|----------------|-------------|
| addenda_page_1 | 2779 | 296 | Faux positifs: ABOVE, BELOW, mots fonctionnels |
| test2_page6 | 1170 | 510 | Codes équipements confondus avec rooms |

### Next: Phase 3.7 — Semantic Refinement

See `docs/WORK_QUEUE_PHASE3_7_SEMANTIC.md`

### Test Gates (Phase 3.4)
| Gate | Description | Test |
|------|-------------|------|
| GATE A | Single page → 3 payloads | `TestGateA_SinglePageGuidePayloads` |
| GATE B | payload_validations present | `TestGateB_PayloadValidations` |
| GATE C | rooms_emitted > 0 on single page | `TestGateC_SinglePageExtraction` |
| DPI | Works at 150 and 300 DPI | `TestDPIRobustness` |

### Key Decisions
- Stability score >= 0.5 acceptable for room payloads (not 0.8)
- Multi-page increases confidence but is NOT required
- See `docs/DECISIONS_Phase3_4.md`

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
## Phase 4 — Render & Viewer

Status: NOT STARTED

Constraints:
- Must remain 100% guide-driven
- No visual heuristics in code
- No semantic assumptions outside the guide
- New test gates required before implementation

No Phase 4 work may begin without:
- Explicit approval
- A validated WORK_QUEUE_PHASE3_RENDER.md
- Defined render test gates