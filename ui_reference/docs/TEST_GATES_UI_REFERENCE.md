# TEST_GATES — UI Reference Demo

These are manual acceptance gates for the reference demo.

Gate 1 PDF master upload works
- Upload a PDF
- UI shows pdf_id and fingerprint

Gate 2 Mapping build works
- Start mapping build
- UI shows mapping status and mapping_version_id when done

Gate 3 Guide analyze works
- Start v1 analyze
- UI shows status updates and guide output

Gate 4 Extraction works
- Start v2 extract
- UI shows extract status steps

Gate 5 Query works
- Query room_number 203
- UI displays matches list with bbox and confidence

Gate 6 Overlay preview works
- Selecting a match draws bbox overlay on the plan image
- Overlay aligns with image dimensions returned by API

Gate 7 Render annotated PDF works
- Render PDF for selected objects
- UI shows output_pdf_url and it opens in browser

Gate 8 No hardcoded geometry
- Reload UI and verify no fixed width height values are used for image display or overlay
- Overlays only appear when API returns bbox and image metadata
