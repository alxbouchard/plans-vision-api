# DECISIONS — UI Reference Demo

Locked decisions.

## Folder isolation
- All demo UI code lives under ui_reference/
- No production code imports or depends on this folder

## Auth
- Primary auth is X-API-Key
- X-Owner-Id may be supported only as legacy toggle

## No hardcoded rules
- UI must not infer doors or rooms from pixels
- UI must not compute bbox by itself
- UI only renders what API returns

## Ambiguity
- If API returns ambiguous true, UI must show the candidates list
- UI must not select one automatically

## Geometry
- UI displays bbox in PNG coordinate space only
- Mapping to PDF is handled by API render endpoints

## No model calls
- UI never calls model directly, only API endpoints
