# Feature Build Visual Guide Phase 1

## Goal

Generate a project specific visual guide explaining how plans are drawn,
based only on what is visually observable.

## Inputs

- One or more PNG pages belonging to the same project.

## Outputs

- Provisional guide for single page projects.
- Stable guide for multi page projects.
- Explicit rejection if conventions are contradictory.

## Processing Steps

1. Guide Builder analyzes the first page.
2. Guide Applier applies rules to subsequent pages.
3. Self Validator classifies each rule:
   - stable
   - partial
   - unstable
4. Guide Consolidator produces:
   - stable guide OR
   - explicit rejection.

## Edge Cases

- One page only produces provisional_only true.
- Contradiction makes the rule unstable.
- All rules unstable refuses the guide.

## Out of Scope

- Object localization.
- Bounding boxes.
- OCR accuracy guarantees.

## Definition of Done

- Outputs are JSON only.
- All rules are classified.
- Rejections are explicit.
- No heuristic parsing exists.
