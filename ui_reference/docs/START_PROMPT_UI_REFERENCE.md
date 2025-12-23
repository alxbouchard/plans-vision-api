# START_PROMPT — UI Reference Demo

Copy and paste this prompt into the coding agent when working on the demo UI.

Read ui_reference/docs/FEATURE_UI_REFERENCE_PDF_FIRST.md,
ui_reference/docs/DECISIONS_UI_REFERENCE.md,
ui_reference/docs/TEST_GATES_UI_REFERENCE.md,
and ui_reference/docs/WORK_QUEUE_UI_REFERENCE.md.

Goal:
Update ui_reference/test-ui.html so it demonstrates the full API pipeline (PDF-first):
project, pdf upload, mapping, analyze, extract, query, render.

Rules:
- No recognition logic in UI
- No hardcoded geometry or dimensions
- Use X-API-Key
- Show ambiguity explicitly
- Keep this folder isolated from production code

Do not modify server code unless explicitly approved.
