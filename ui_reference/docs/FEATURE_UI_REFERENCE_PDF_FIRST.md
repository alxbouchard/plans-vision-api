# Feature UI Reference PDF First Demo

Status: READY

This document specifies the official reference demo UI for plans-vision-api.

## Goal

Provide a PDF-first demo UI that lets a user run the full pipeline:

1 Create project
2 Upload PDF master
3 Build mapping PDF to internal PNG
4 Run Phase 1 analyze guide
5 Run Phase 2 extract objects
6 Run Phase 2 query (example room 203)
7 Render annotated PDF
8 Open the annotated PDF output

The UI must visually show:
- statuses
- outputs
- overlays on plan images

## Principles

- PDF master is the truth
- PNGs are internal for analysis only
- Zero recognition logic in UI
- UI uses API responses only
- Ambiguity must be visible, never hidden

## Scope

In scope
- PDF-first workflow
- v1 guide flow visibility
- v2 extract and query visibility
- v3 mapping and render visibility
- basic PNG overlay preview using returned bbox
- links to open output annotated PDF

Out of scope
- a full viewer product
- editing annotations
- advanced UX or styling work
- any attempt to guess objects locally

## Definition of Done

- A complete demo can be executed without touching code
- No hardcoded image dimensions are used
- All displayed overlays use API returned bbox and image metadata
- Rendered PDF link is clickable and opens
