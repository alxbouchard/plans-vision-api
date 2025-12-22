# WORK_QUEUE — Allowed Autonomous Tasks

This file defines what the agent may execute autonomously without asking.
The agent may ONLY work on tasks listed here.

If a task would expand scope, change product phase, or add a new feature not listed here,
the agent MUST stop and ask.

---

## Phase 1 — Build Visual Guide (LOCKED)

Status: LOCKED  
No further feature work is allowed in Phase 1.

Allowed:
- Documentation updates (clarity only)
- Non-behavioral refactors
- Additional tests that do not change behavior

---

## Phase 1.5 — Hardening for SaaS (Allowed Autonomous Work)

Goal: Make the API production-grade as a standalone monetizable service WITHOUT adding Phase 2 features.

### 1) Public API contract and schemas
- Add docs/API_CONTRACT_v1.md describing endpoints, request/response JSON examples, and error codes.
- Ensure OpenAPI schema includes response models for /status and /guide.
- Add schema versioning in responses: schema_version field.

### 2) Multi-tenant foundation
- Implement API key auth middleware:
  - Required header: X-API-Key
  - Reject with 401/403 using standardized error format
- Introduce tenant_id in DB models and enforce isolation in queries.
- Add rate limiting (simple fixed window acceptable for v1).
- Add quotas:
  - max projects per tenant
  - max pages per project
  - max pages per month
- Add usage counters (pages_processed).

### 3) Idempotency and retries
- Add idempotency key support for:
  - create project
  - upload page
  - analyze start
- Ensure re-sent requests do not duplicate resources.
- Add safe retry logic around model calls with exponential backoff.

### 4) Error taxonomy enforcement
- Ensure every failure path maps to a documented error_code in docs/ERRORS.md.
- Ensure /status returns structured step errors when pipeline fails.
- Add tests for each major error code.

### 5) Observability
- Add structured logging fields:
  - timestamp
  - tenant_id
  - project_id
  - step
  - duration_ms
  - outcome
  - error_code
- Add request_id correlation and include it in responses.
- Add minimal metrics via logs for:
  - pages_processed
  - guides_generated
  - guides_rejected
  - avg_latency_per_step

### 6) Storage hardening
- Validate uploads:
  - PNG only
  - max file size
  - max pixel dimensions
- Ensure storage paths are tenant-scoped.
- Add cleanup policy for temporary artifacts.

### 7) Dataset and fixtures
- Add a testdata folder with:
  - 1 real plan set (3 pages) for regression tests
  - 1 contradiction set (2 pages) for rejection tests
- Ensure fixtures do not include sensitive client data.

### 8) Release hygiene
- Add docs/CHANGELOG.md with semantic versioning notes.
- Add docs/SECURITY.md for secret handling and env vars.
- Add docs/RUNBOOK.md for run, debug, triage.
- Add a Makefile or scripts:
  - make test
  - make run

Allowed refactors:
- Refactor for readability if behavior and schemas remain unchanged.
- Improve code structure to reduce duplication.

Forbidden:
- Object extraction (rooms, doors, windows, etc.)
- Bounding boxes or polygons
- PDF annotation output
- Viewer-specific outputs or UI work

---

## Phase 2 — Extraction and Viewer Outputs (NOT STARTED)

No Phase 2 work is allowed unless explicitly approved.

Examples requiring approval:
- rooms detection and “Classe 203” queries
- doors/windows extraction
- PDF in → annotated PDF out
- JSON overlay for viewer
- searchable object index
