# TEST_GATES_PHASE2 — Mandatory gates for Extraction

All gates must pass before Phase 2 is considered complete.

## Gate A Page classification required
- Given a project with pages
- When extraction starts
- Then every page must have page_type stored
- And non plan pages must not run plan extraction

## Gate B Rooms extracted on consistent_set
- Using testdata/consistent_set
- Extract produces at least 1 room object with:
  - room_number present
  - bbox present
  - confidence_level not low

## Gate C Query room number works
- After extraction and index build
- GET /v2/projects/{id}/query?room_number=203 returns:
  - status 200
  - matches length >= 1
  - ambiguous false if unique
  - bbox present in match

## Gate D Ambiguous query is explicit
- A query expected to match multiple results
- Must return ambiguous true and multiple matches
- Must not pick one arbitrarily

## Gate E Doors extracted with conservative rules
- At least 1 door object exists on plan pages
- Door_type may be unknown if not clear
- No doors extracted on non plan pages

## Gate F Schedule parsing isolated
- For a schedule page
- Extract table grid structure
- Ensure schedule extraction does not run on plan pages

## Gate G Schema enforcement
- All extraction outputs validate against schemas
- Invalid model output fails loudly

## Gate H Deterministic index
- Index keys are deterministic
- Re running extraction without changes does not change IDs for the same objects
