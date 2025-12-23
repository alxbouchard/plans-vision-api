# API_CONTRACT_Render_v3

Schema version for this contract: 3.1
This contract defines PDF master anchoring and rendering outputs.

Auth: X-API-Key required

## 1 Upload PDF master

POST /v3/projects/{project_id}/pdf
multipart form field: file

Response 201
```json
{
  "schema_version": "3.1",
  "project_id": "uuid",
  "pdf_id": "uuid",
  "page_count": 42,
  "fingerprint": "sha256",
  "stored_at": "ISO8601"
}
```

Errors
- 400 INVALID_PDF
- 401 API_KEY_MISSING
- 403 API_KEY_INVALID

## 2 Build mapping for PDF

POST /v3/projects/{project_id}/pdf/{pdf_id}/build-mapping

Response 202
```json
{
  "schema_version": "3.1",
  "project_id": "uuid",
  "pdf_id": "uuid",
  "mapping_job_id": "uuid",
  "status": "processing"
}
```

GET /v3/projects/{project_id}/pdf/{pdf_id}/mapping/status

Response 200
```json
{
  "schema_version": "3.1",
  "project_id": "uuid",
  "pdf_id": "uuid",
  "mapping_version_id": "uuid|null",
  "overall_status": "pending|running|completed|failed",
  "current_step": "rasterize|compute_page_transform|null",
  "errors": []
}
```

## 3 Get mapping metadata

GET /v3/projects/{project_id}/pdf/{pdf_id}/mapping

Response 200
```json
{
  "schema_version": "3.1",
  "project_id": "uuid",
  "pdf_id": "uuid",
  "fingerprint": "sha256",
  "mapping_version_id": "uuid",
  "pages": [
    {
      "page_number": 1,
      "png_width": 8000,
      "png_height": 5200,
      "pdf_width_pt": 612,
      "pdf_height_pt": 792,
      "rotation": 0,
      "mediabox": [0,0,612,792],
      "cropbox": [0,0,612,792],
      "transform": { "type": "affine", "matrix": [a,b,c,d,e,f] }
    }
  ]
}
```

## 4 Query with PDF anchored geometry

GET /v3/projects/{project_id}/query
Query params: room_number, room_name, door_tag, type, limit

Response 200
```json
{
  "schema_version": "3.1",
  "project_id": "uuid",
  "query": { "room_number": "203" },
  "ambiguous": false,
  "matches": [
    {
      "object_id": "room_203",
      "type": "room",
      "page_number": 12,
      "label": "CLASSE 203",
      "confidence": 0.92,
      "confidence_level": "high",
      "geometry_png": { "type": "bbox", "bbox": [100,200,300,250] },
      "geometry_pdf": { "type": "rect", "rect": [x1,y1,x2,y2] },
      "reasons": ["page_type_plan","guide_supported_evidence","unique_index_key"],
      "trace": {
        "pdf_id": "uuid",
        "pdf_fingerprint": "sha256",
        "mapping_version_id": "uuid",
        "guide_version_id": "uuid",
        "extraction_run_id": "uuid",
        "index_version_id": "uuid"
      }
    }
  ]
}
```

Error
- 409 PDF_MASTER_REQUIRED
- 409 MAPPING_REQUIRED

## 5 Render annotated PDF

POST /v3/projects/{project_id}/render/pdf

Request
```json
{
  "schema_version": "3.1",
  "pdf_id": "uuid",
  "mapping_version_id": "uuid",
  "objects": ["room_203","door_203"],
  "layers": ["rooms","doors"],
  "style": {
    "mode": "highlight",
    "include_labels": true,
    "min_confidence_level": "medium"
  }
}
```

Response 202
```json
{
  "schema_version": "3.1",
  "project_id": "uuid",
  "pdf_id": "uuid",
  "render_job_id": "uuid",
  "status": "processing"
}
```

GET /v3/projects/{project_id}/render/pdf/{render_job_id}

Response 200
```json
{
  "schema_version": "3.1",
  "render_job_id": "uuid",
  "status": "completed",
  "output_pdf_url": "https://...",
  "trace": {
    "pdf_fingerprint": "sha256",
    "mapping_version_id": "uuid",
    "extraction_run_id": "uuid"
  }
}
```

Errors
- 409 PDF_MISMATCH
- 409 MAPPING_MISMATCH
- 422 NO_MATCHES

## 6 Render annotations only

POST /v3/projects/{project_id}/render/annotations

Request
```json
{
  "schema_version": "3.1",
  "pdf_id": "uuid",
  "mapping_version_id": "uuid",
  "objects": ["room_203"],
  "format": "json"
}
```

Response 200
```json
{
  "schema_version": "3.1",
  "pdf_id": "uuid",
  "format": "json",
  "annotations": [
    {
      "page_number": 12,
      "type": "rect",
      "rect": [x1,y1,x2,y2],
      "label": "CLASSE 203",
      "object_id": "room_203",
      "confidence_level": "high"
    }
  ]
}
```

Optional
- format xfdf supported later

## Standard error format

```json
{
  "schema_version": "3.1",
  "error_code": "STRING",
  "message": "Human readable message",
  "recoverable": true
}
```
