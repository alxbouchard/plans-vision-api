# UI Reference Demo — plans-vision-api

This folder contains the official reference demo UI for plans-vision-api.

Purpose:
- Demonstrate the full end-to-end pipeline using the public API
- Provide a visual debugging tool for development and sales demos
- Serve as the reference integration blueprint for other clients and apps

Non-goals:
- This is not a production UI
- This is not a viewer product
- No business logic or recognition rules live here

Core rules:
- The UI is a passive consumer of the API
- The PDF master is the source of truth
- No hardcoded geometry — all dimensions from API responses
- Ambiguity is shown explicitly, never hidden

## Pipeline Steps

The demo implements a 7-step PDF-first workflow:

1. Create project
2. Upload PDF master (v3)
3. Build mapping — converts PDF to internal PNG with coordinate transforms (v3)
4. Analyze — builds visual guide from plan conventions (v1)
5. Extract — extracts rooms, doors, schedules using the guide (v2)
6. Query — queries objects by room number (v2)
7. Render — creates annotated PDF with highlights (v3)

## Entry point

test-ui.html

## Setup

1. Start the API locally: `uvicorn src.api.app:app --reload`
2. Open test-ui.html in a browser
3. Enter your API key (X-API-Key)
4. Run through the pipeline steps

## Auth

- Uses X-API-Key header (official)
- No legacy X-Owner-Id support in this demo

## Security

- Do not commit real API keys
- Use local keys for demo

Date: 2025-12-23
