# Error Taxonomy

All API errors follow a consistent JSON format with a documented error code.

## Error Response Format

```json
{
  "schema_version": "1.0",
  "error_code": "GUIDE_REJECTED_CONTRADICTION",
  "message": "Visual conventions contradict across pages",
  "details": null
}
```

---

## AUTHENTICATION (4xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `API_KEY_MISSING` | 401 | No X-API-Key or X-Owner-Id header provided |
| `API_KEY_INVALID` | 401 | API key not recognized |
| `TENANT_DISABLED` | 403 | Tenant account has been disabled |
| `INVALID_OWNER_ID` | 400 | X-Owner-Id is not a valid UUID |

## AUTHORIZATION / QUOTAS (4xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `QUOTA_EXCEEDED` | 403 | Resource limit reached (projects, pages, monthly usage) |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests in time window |

## VALIDATION (4xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request body failed Pydantic validation |
| `INVALID_IMAGE_FORMAT` | 415 | Only PNG images are accepted |
| `INVALID_IDEMPOTENCY_KEY` | 400 | Idempotency key too long (max 256 chars) |
| `PROJECT_NOT_FOUND` | 404 | Project ID does not exist or not owned by tenant |
| `PAGE_NOT_FOUND` | 404 | Page ID does not exist |
| `GUIDE_NOT_FOUND` | 404 | No visual guide exists for project |

## CONFLICT (4xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `PROJECT_ALREADY_VALIDATED` | 409 | Cannot add pages to validated project |
| `PROJECT_PROCESSING` | 409 | Cannot modify project during analysis |
| `ANALYSIS_ALREADY_RUNNING` | 409 | Analysis already in progress |

## BUSINESS LOGIC (4xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NO_PAGES` | 422 | At least 1 page required to start analysis |
| `SINGLE_PAGE_PROVISIONAL_ONLY` | 200 | Single-page projects return provisional guide only (informational) |
| `GUIDE_REJECTED_CONTRADICTION` | 200 | Guide rejected due to contradicting visual rules |
| `GUIDE_REJECTED_NO_STABLE_RULES` | 200 | Guide rejected due to insufficient stable rules |

## PIPELINE ERRORS (5xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `PIPELINE_FAILED` | 500 | Pipeline execution failed at a specific step |
| `GUIDE_BUILDER_FAILED` | 500 | Guide Builder agent failed |
| `GUIDE_APPLIER_FAILED` | 500 | Guide Applier agent failed |
| `SELF_VALIDATOR_FAILED` | 500 | Self-Validator agent failed |
| `GUIDE_CONSOLIDATOR_FAILED` | 500 | Guide Consolidator agent failed |

## MODEL ERRORS (5xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `MODEL_TIMEOUT` | 503 | Model API call timed out |
| `MODEL_INVALID_OUTPUT` | 500 | Model returned unparseable JSON |
| `MODEL_RATE_LIMITED` | 503 | Model API rate limit hit |
| `VISION_ERROR` | 500 | General vision model error |

## SYSTEM ERRORS (5xx)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INTERNAL_ERROR` | 500 | Unhandled internal error |
| `STORAGE_FAILURE` | 500 | File storage operation failed |
| `DATABASE_ERROR` | 500 | Database operation failed |

---

## Pipeline Status Errors

When pipeline fails, `/status` returns structured error info:

```json
{
  "schema_version": "1.0",
  "project_id": "uuid",
  "status": "failed",
  "current_step": "guide_applier",
  "error": {
    "error_code": "MODEL_INVALID_OUTPUT",
    "message": "Guide Applier returned invalid JSON",
    "step": "guide_applier",
    "page": 2
  }
}
```
