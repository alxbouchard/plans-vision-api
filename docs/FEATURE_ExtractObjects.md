# Feature Object Extraction and Localization Phase 2

## Status

Not implemented.
This document defines future scope only.

## Goal

Locate concrete objects on plan pages using the validated visual guide.

Examples:
- Rooms such as CLASSE 203
- Doors
- Windows
- Stairs

## Preconditions

- A stable visual guide MUST exist.
- Page type MUST be classified as plan.

## Outputs

- Object index searchable by label and number.
- Geometry as bbox or polygon.
- Confidence per object.

## Non Goals

- No 100 percent accuracy promise.
- No inference without guide support.

## Risks

- Mixing extraction with guide logic.
- Viewer specific assumptions.

## Definition of Done Future

- Queries like show room 203 are possible.
- Confidence is explicit.
- Objects can be refused if ambiguous.
