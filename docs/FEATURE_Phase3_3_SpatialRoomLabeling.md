# FEATURE_Phase3_3_SpatialRoomLabeling.md

Purpose
Improve room extraction so that user queries like "203" can locate a room label even when the same number exists as door numbers like "203" or "203-1".

Problem statement
In real school plans, the token 203 can appear as:
- A room label block (example: "CLASSE 203")
- A door number near a door (example: "203" or "203-1")
The API must not conflate them.

Approach (no hardcoding)
1 Detect candidate text blocks (bbox + text) using a minimal vision pass
2 Identify candidate room label blocks using only measurable evidence:
  - presence of a 2 to 4 digit token in the block text
  - optional room-region inference, conservative only
3 Disambiguate using door neighborhood evidence:
  - if a numeric token is close to a door geometry or door label bbox, treat it as a door number
  - if conflict, ambiguity true
4 Output rooms with label_bbox always set, room_region_bbox nullable

Inputs
- Page image bytes
- Existing extracted doors (bbox + door_number if available)
- Detected text blocks

Outputs
- ExtractedRoom candidates with:
  - room_number (nullable)
  - room_name (nullable)
  - label_bbox (required when emitted)
  - ambiguity (bool)
  - ambiguity_reason (nullable)

Runtime controls
- Feature flag ENABLE_PHASE3_3_SPATIAL_LABELING
- ExtractionPolicy:
  - conservative for stable guide
  - relaxed for provisional_only mode (still no invention)

Non goals
- Full OCR of the page
- Polygon room segmentation
- Hardcoded language keywords

Failure behavior
- If detector fails, pipeline continues with existing extractor, but logs a structured error
- Never return a room if the only evidence is a single number with no supporting context

Observability
Emit structured logs:
- phase3_3_detector_called
- phase3_3_text_blocks_count
- phase3_3_room_candidates_count
- phase3_3_rooms_emitted_count
