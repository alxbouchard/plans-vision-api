# Feature Extract Objects and Build Query Index Phase 2

Status: READY TO IMPLEMENT

This document is the executable specification for Phase 2.
It is designed to be followed by an autonomous coding agent.

## Goal

From plan pages of a single project, extract and localize key objects and produce:
1) a per page overlay payload for viewers
2) a project wide searchable index that supports queries like:
   - show room 203
   - list all doors
   - highlight all rooms of type CLASSE

The system must remain honest.
If an object cannot be localized reliably, it must be omitted or marked ambiguous with explicit confidence and reason.

## Preconditions

- Phase 1 must be complete and locked.
- A stable visual guide must exist OR the project must be explicitly marked provisional_only.
- Page type classification must exist and be used to gate extraction.
- Output schemas must be strict JSON validated by Pydantic.

## In Scope

Object types to support in Phase 2.0

A Rooms
- Detect room labels (name and number) and associate to a room region.
- Output room_id, room_number, room_name, geometry, confidence, sources.

B Doors
- Detect door openings and swings when visible.
- Output door_id, door_type (single, double, unknown), geometry, confidence, sources.

C Windows
- Detect window symbols when they are visually distinguishable from doors.
- Output window_id, geometry, confidence, sources.

D Vertical circulation
- Stairs and elevators if labeled or symbol is consistent.
- Output type, label if present, geometry, confidence.

E Schedules tables
- For pages classified as schedule, extract table structure and row items.
- Output schedule_id, table grid, row objects, confidence.

## Out of Scope

- Mechanical and electrical symbol semantics.
- Full wall vectorization.
- Dimensions and measurements.
- 100 percent completeness guarantees.
- PDF annotation output in Phase 2.0.
- Polygon perfect segmentation for every room.

## Outputs

Phase 2 produces three core artifacts:

1) PageOverlay JSON
- A list of drawable objects for a viewer.
- Coordinate space is image pixels of the stored PNG for that page.

2) ProjectIndex JSON
- Search mappings:
  - rooms_by_number
  - rooms_by_name
  - objects_by_type
- Allows deterministic query resolution.

3) Query responses
- Endpoint that returns a list of matches with geometry and confidence.

## Coordinate and Geometry Rules

- Coordinate system is the stored PNG pixel space.
- Origin is top left.
- Geometry types supported:
  - bbox: [x, y, w, h]
  - polygon: list of points for future use, optional in Phase 2.0

Phase 2.0 requires bbox.
Polygon is optional and may be added later as Phase 2.1.

## Confidence Rules

Every object must include:
- confidence: float 0.0 to 1.0
- confidence_level: high, medium, low
- sources: list of evidence strings such as:
  - text_detected
  - boundary_detected
  - symbol_pattern_matched
  - guide_rule_supported

Rules:
- If confidence_level is low, object must include reason and may be omitted from index by default.
- The system must never return a single match as definitive if multiple candidates are plausible.

## Page Type Classification

Every page must be classified before extraction into one of:
- plan
- schedule
- notes
- legend
- detail
- unknown

Extraction rules:
- rooms and doors run only on plan pages.
- schedule extraction runs only on schedule pages.
- legend pages are used only for guide enrichment, not extraction.

## Pipeline

Phase 2 pipeline per project:

Step 1 Ensure stable guide exists
- If guide missing, return 409 GUIDE_REQUIRED

Step 2 Classify all pages
- Store per page page_type with confidence

Step 3 Extract per page objects
- plan pages: rooms, doors, windows, circulation
- schedule pages: tables and rows

Step 4 Build project index
- deterministic keys
- ambiguity handling

Step 5 Serve query endpoints
- return list of candidates with score

## Definition of Done

Phase 2 is done when:

- Endpoints defined in API_CONTRACT_v2.md exist and match schemas.
- TEST_GATES_PHASE2 all pass.
- Using the fixture consistent_set, a query for an existing room number returns at least 1 match with bbox and confidence.
- Using the contradiction_set, extraction does not invent semantics and still behaves deterministically.
- Ambiguous queries return multiple candidates or explicit ambiguity errors.
- All outputs are strict JSON validated by schema.
