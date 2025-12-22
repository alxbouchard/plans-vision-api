# Mandatory Test Gates

These tests MUST exist and MUST pass.

## Gate 1 Single Page

Input 1 page  
Expected:
- provisional_only true
- no stable rules

## Gate 2 Consistent Pages

Input 2 or more consistent pages  
Expected:
- stable guide generated
- stable rules greater than 0

## Gate 3 Contradiction

Input 2 pages with conflicting conventions  
Expected:
- guide rejected
- explicit rejection reason

## Gate 4 Invalid Model Output

Input malformed model JSON  
Expected:
- pipeline fails loudly
- no silent fallback

## Gate 5 Schema Enforcement

Input output violating schema  
Expected:
- validation error
