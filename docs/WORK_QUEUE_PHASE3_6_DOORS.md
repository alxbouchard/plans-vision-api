# WORK_QUEUE_PHASE3_6_DOORS.md

## Goal
Extract doors (door_number + bbox) from a single page without hardcoded logic.
No "arc = door" assumptions. All intelligence from Visual Guide payloads.

## Prerequisites
- Phase 3.5 rooms extraction working
- Visual Guide produces door payloads

## Ticket 3.6.1: Door number payload in guide
- GuideBuilder must detect door number patterns
- New payload: token_detector(token_type="door_number")
- Pattern from guide (e.g., "\d{3}-\d" for "203-1")

### Ticket 3.6.2: Exclude payload for disambiguation
- Payload kind="exclude" to prevent room_number/door_number confusion
- Example: door numbers often have "-" suffix (203-1, 203-2)
- Room numbers are plain (203, 204)

### Ticket 3.6.3: DoorExtractor uses tokens
- Filter tokens by door_number payload
- Exclude tokens matching room_number pattern
- Emit doors with bbox from token

### Ticket 3.6.4: Door symbol detection (future)
- New payload kind="symbol_detector"
- Guide describes visual symbol (arc, swing direction)
- Engine executes payload without assumptions

## Gate Phase 3.6
```
GATE_3.6A: addenda_page_1 -> doors_emitted > 0
GATE_3.6B: Test2 floorplan -> doors_emitted > 0
Logs: doors_emitted, rejected_excluded, door_tokens_found
```

## Stop Conditions
- No hardcoded "arc = door"
- No keyword lists for door detection
- If symbol detection needed: add payload, not code

## Definition of Done
- doors_emitted > 0 on both fixtures
- All door logic from guide payloads
- Logs explain rejections clearly
