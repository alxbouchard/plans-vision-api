# TEST_GATES_RENDER

All gates must pass before render feature is considered complete.

## Gate 1 Fingerprint mismatch refusal
- If pdf_id fingerprint differs from mapping fingerprint, render must refuse with PDF_MISMATCH

## Gate 2 Mapping required
- If mapping_version_id missing, endpoints refuse with MAPPING_REQUIRED

## Gate 3 Coordinate transform correctness
- For known synthetic bbox in PNG space, computed PDF rect matches expected within tolerance

## Gate 4 Rotation coverage
- Mapping handles rotation 0, 90, 180, 270 with tests

## Gate 5 Cropbox coverage
- Mapping respects cropbox and mediabox differences with tests

## Gate 6 Renderer is pure
- Renderer performs zero model calls
- Test enforces no calls to model client during render endpoints

## Gate 7 PDF output contains annotations
- Output PDF contains expected annotation objects
- Annotation count and page numbers match requested objects

## Gate 8 Annotated PDF is reproducible
- Same inputs with same extraction_run_id produce identical annotations geometry and IDs
