# Feature Render Master PDF Outputs

Status: READY TO IMPLEMENT

This feature defines the final output layer that anchors all visual results to the PDF master.
PNG images may be generated internally for AI analysis, but the master PDF remains the source of truth.

No recognition rules are introduced here. Rendering uses only existing extracted objects and mapping.

## Goal

Provide wow outputs for a non technical superintendent:
- open the master PDF and see highlights on the correct locations
- share a single link or annotated PDF
- always see confidence and traceability

## Inputs

- A master PDF stored for the project (pdf_id and fingerprint)
- A mapping_version_id that maps PNG pixel coordinates to PDF page coordinates
- Extracted objects from Phase 2 (bbox in PNG coordinates, object_id, type, label, confidence)

## Outputs

A Data output always
- JSON results containing objects, reasons, and trace

B Visual outputs choose one or both
1 Annotated PDF output (PDF in to PDF out)
2 Annotations only output (JSON annotations and optional XFDF)
3 Annotated PNG preview optional

## Preconditions

- Phase 1 locked and Phase 2 extraction complete for the project
- A master PDF has been uploaded and fingerprinted
- A mapping exists for that exact PDF fingerprint

## In Scope

- Master PDF upload and fingerprinting
- Per page mapping generation
- PNG bbox to PDF rect conversion
- Render annotations into a derived PDF
- Export annotations as JSON and optional XFDF
- Traceability and safety checks

## Out of Scope

- Viewer UI
- OCR based text highlight as a requirement
- Polygon perfect segmentation
- Any new detection or recognition logic

## Safety and Honesty

- If PDF fingerprint mismatches, refuse render
- If mapping missing, refuse render
- If object confidence is low, default behavior is to return candidates and not annotate unless requested

## Definition of Done

- All endpoints defined in API_CONTRACT_Render_v3 are implemented
- TEST_GATES_RENDER all pass, including rotation and cropbox mapping
- Renderer performs zero model calls
- Output PDF opens in standard viewers and contains expected annotations
