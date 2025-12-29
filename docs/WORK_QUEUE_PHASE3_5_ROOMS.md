# WORK_QUEUE_PHASE3_5_ROOMS.md

## Goal
Extract rooms (room_name + room_number + bbox) from a single page using tokens-first approach.
No Vision API calls needed if PyMuPDF tokens are available.

## Prerequisites
- Phase 3.3 FROZEN (SpatialRoomLabeler is execution engine only)
- Phase 3.4 stable guide produces 3 mandatory payloads

## Phase 0: Token Unification (BLOCKING)

### Ticket 0.1: TextToken schema
- Create `src/extraction/tokens.py`
- Define `TextToken(text, bbox, confidence, source, page_id)`
- Define `PageRasterSpec(width_px, height_px, dpi, rotation)`
- All bbox in pixel space (same as PNG)

### Ticket 0.2: PyMuPDFTokenProvider
- Extract words/lines from PDF via PyMuPDF
- Convert PDF coordinates to pixel coordinates
- Return list[TextToken] with source="pymupdf"
- Confidence = 1.0 (vector text is exact)

### Ticket 0.3: VisionTokenProvider adapter
- Wrap existing TextBlockDetector
- Return list[TextToken] with source="vision"
- Confidence from model response

### Ticket 0.4: TokenMerger
- Merge tokens from multiple sources
- Dedup by IoU > 0.5 and text similarity
- Priority: pymupdf > vision > ocr

### Gate Phase 0
```
GATE_0A: addenda_page_1 -> tokens contain room names AND numbers
GATE_0B: Test2 floorplan -> tokens contain room names AND numbers
Logs: tokens_count_by_source, tokens_final_count
```

## Phase 3.5: Rooms Extraction Tokens-First

### Ticket 3.5.1: Pipeline uses TokenProvider
- If PDF available: use PyMuPDFTokenProvider
- Else: use VisionTokenProvider (TextBlockDetector)
- Pass tokens to SpatialRoomLabeler instead of text_blocks

### Ticket 3.5.2: SpatialRoomLabeler accepts TextToken
- Adapter to convert TextToken -> TextBlockLike
- No modification to frozen labeler logic

### Ticket 3.5.3: Room extraction bypasses page_type
- If room_payloads_ready=true: attempt extraction
- page_type is informative only, not blocking

### Gate Phase 3.5
```
GATE_3.5A: addenda_page_1 -> rooms_emitted > 0
GATE_3.5B: Test2 floorplan -> rooms_emitted > 0
GATE_3.5C: No Vision API call if PyMuPDF tokens available
Logs: tokens_found_by_type, pairs_formed, rooms_emitted
```

## Stop Conditions
- If any change requires modifying SpatialRoomLabeler: STOP, RFC
- If hardcode needed: STOP, add payload to guide instead

## Definition of Done
- rooms_emitted > 0 on both fixtures
- No hardcoded keywords
- Logs explain failures clearly
