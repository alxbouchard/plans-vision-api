# DECISIONS_Render

Locked decisions to keep rendering bulletproof and non hardcoded.

## Master is the truth
- The master PDF remains the authoritative document
- PNGs are internal artifacts used for analysis only

## No recognition in renderer
- Rendering performs zero model calls
- Rendering never reads pixels to infer objects
- Rendering uses extracted objects and mapping only

## Mapping is required
- All PDF anchored geometry must be derived from mapping_version_id
- If mapping missing, refuse

## Fingerprint safety
- Every render request must specify pdf_id and mapping_version_id
- The server must verify stored fingerprint matches
- If mismatch, refuse with PDF_MISMATCH

## Geometry
- Phase 3.1 uses bbox derived rect annotations
- Polygon rendering optional later, not required

## Confidence policy
- Default min_confidence_level is medium for rendering
- Low confidence objects are excluded unless explicitly requested

## Traceability
- Every output includes trace ids:
  - pdf_id, pdf_fingerprint, mapping_version_id
  - guide_version_id, extraction_run_id, index_version_id

## Portability
- Use standard PDF annotations:
  - square or rectangle annotation with optional text label
- Do not rely on proprietary viewer features
