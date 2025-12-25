# Phase 3.3 Operator Notes

Date: 2025-12-24

## Why this phase
Some documents reuse the same digits in different roles:
- Room label: CLASSE 203
- Door label: 203
- Door label: 203-1

Text-only extraction confuses these. Phase 3.3 uses geometry evidence to separate them.

## Expected after Phase 3.3
- /v2/extract returns room objects for interior label blocks
- /v2/query?room_number=203 returns matches
- Door numbers remain door numbers
- Ambiguity is explicit when evidence is insufficient
