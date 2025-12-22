# API_CONTRACT_v2 — Extraction and Query

This contract extends v1.
All responses include schema_version.

## Base

- Base path: /v2
- Auth: X-API-Key required
- Idempotency: Idempotency-Key supported

## New Resources

- ExtractionJob
- PageClassification
- ExtractedObject
- PageOverlay
- ProjectIndex

## Endpoints

### 1 Start extraction
POST /v2/projects/{project_id}/extract

Response 202
```json
{
  "schema_version": "2.0",
  "project_id": "uuid",
  "status": "processing",
  "job_id": "uuid"
}
```

Errors
- 409 GUIDE_REQUIRED
- 404 PROJECT_NOT_FOUND
- 409 EXTRACT_ALREADY_RUNNING

### 2 Extraction status
GET /v2/projects/{project_id}/extract/status

Response 200
```json
{
  "schema_version": "2.0",
  "project_id": "uuid",
  "job_id": "uuid",
  "overall_status": "pending|running|completed|failed",
  "current_step": "classify_pages|extract_objects|build_index|null",
  "steps": [
    {
      "name": "classify_pages",
      "status": "pending|running|completed|failed",
      "error": null
    }
  ]
}
```

### 3 Get page overlay
GET /v2/projects/{project_id}/pages/{page_id}/overlay

Response 200
```json
{
  "schema_version": "2.0",
  "project_id": "uuid",
  "page_id": "uuid",
  "image": { "width": 8000, "height": 5200 },
  "page_type": "plan",
  "objects": [
    {
      "id": "room_203",
      "type": "room",
      "label": "CLASSE 203",
      "room_number": "203",
      "room_name": "CLASSE",
      "geometry": { "type": "bbox", "bbox": [100, 200, 300, 250] },
      "confidence": 0.92,
      "confidence_level": "high",
      "sources": ["text_detected", "boundary_detected"]
    }
  ]
}
```

### 4 Get project index
GET /v2/projects/{project_id}/index

Response 200
```json
{
  "schema_version": "2.0",
  "project_id": "uuid",
  "generated_at": "ISO8601",
  "rooms_by_number": {
    "203": ["room_203"]
  },
  "objects_by_type": {
    "door": ["door_001"]
  }
}
```

### 5 Query
GET /v2/projects/{project_id}/query

Query params
- room_number=203
- room_name=CLASSE
- type=door

Response 200
```json
{
  "schema_version": "2.0",
  "project_id": "uuid",
  "query": { "room_number": "203" },
  "matches": [
    {
      "object_id": "room_203",
      "page_id": "uuid",
      "score": 0.92,
      "geometry": { "type": "bbox", "bbox": [100, 200, 300, 250] },
      "label": "CLASSE 203",
      "confidence_level": "high",
      "reasons": ["unique_room_number_match"]
    }
  ],
  "ambiguous": false
}
```

Ambiguous response
```json
{
  "schema_version": "2.0",
  "project_id": "uuid",
  "query": { "room_name": "BUREAU" },
  "matches": [ ... ],
  "ambiguous": true,
  "message": "Multiple candidates found"
}
```

## Standard error format

```json
{
  "schema_version": "2.0",
  "error_code": "STRING",
  "message": "Human readable message",
  "recoverable": true
}
```
