# API_CONTRACT_v1 — plans-vision-api (SaaS)

This document defines the public API contract for v1.

This contract is focused on Phase 1 (Visual Guide) and Phase 1.5 (Hardening).
Phase 2 endpoints are explicitly out of scope.

---

## Base URL

- Base path: /v1
- Authentication: X-API-Key header (required)

---

## Conventions

### Content types
- Requests: application/json unless file upload
- Responses: application/json

### Idempotency (recommended for v1.5)
- Header: Idempotency-Key
- Behavior: same request with same key must not create duplicates

### Schema versioning
All successful responses MUST include:
- schema_version: "1.0"

---

## Endpoints

### 1) Create project
POST /v1/projects

Response 201
```json
{
  "schema_version": "1.0",
  "project_id": "uuid",
  "status": "draft",
  "created_at": "ISO8601"
}
```

Errors
- 401 API_KEY_MISSING
- 403 API_KEY_INVALID

---

### 2) Upload page
POST /v1/projects/{project_id}/pages
- Content-Type: multipart/form-data
- Field: file (PNG only)

Response 200
```json
{
  "schema_version": "1.0",
  "page_id": "uuid",
  "project_id": "uuid",
  "page_index": 1,
  "width": 8000,
  "height": 5200,
  "mime_type": "image/png"
}
```

Validation rules
- PNG only
- size <= MAX_UPLOAD_BYTES
- dimensions <= MAX_PIXELS (width * height)

Errors
- 400 INVALID_IMAGE_FORMAT
- 404 PROJECT_NOT_FOUND
- 409 PROJECT_LOCKED

---

### 3) Start analysis
POST /v1/projects/{project_id}/analyze

Response 202
```json
{
  "schema_version": "1.0",
  "project_id": "uuid",
  "status": "processing",
  "started_at": "ISO8601"
}
```

Errors
- 404 PROJECT_NOT_FOUND
- 409 ANALYZE_ALREADY_RUNNING

---

### 4) Get status
GET /v1/projects/{project_id}/status

Response 200
```json
{
  "schema_version": "1.0",
  "project_id": "uuid",
  "overall_status": "pending|running|completed|failed",
  "current_step": "guide_builder|guide_applier|self_validator|guide_consolidator|null",
  "steps": [
    {
      "name": "guide_builder",
      "status": "pending|running|completed|failed",
      "started_at": "ISO8601|null",
      "completed_at": "ISO8601|null",
      "error": null
    }
  ],
  "last_error": null,
  "updated_at": "ISO8601"
}
```

---

### 5) Get guide
GET /v1/projects/{project_id}/guide

Response 200
```json
{
  "schema_version": "1.0",
  "project_id": "uuid",
  "has_provisional": true,
  "has_stable": false,
  "provisional": { "type": "GuideBuilderOutput", "data": {} },
  "stable": null,
  "confidence_report": {
    "can_generate_final": false,
    "rejection_reason": "single_page_no_validation"
  }
}
```

Rejection response (business)
Response 422
```json
{
  "schema_version": "1.0",
  "error_code": "GUIDE_REJECTED_CONTRADICTION",
  "message": "Visual conventions contradict across pages",
  "recoverable": false
}
```

---

## Standard error format
All errors MUST follow:
```json
{
  "schema_version": "1.0",
  "error_code": "STRING",
  "message": "Human readable message",
  "recoverable": true
}
```

---

## Rate limits (v1.5 target)
- 60 req/min per API key (initial default)
- Reject with 429 RATE_LIMITED
