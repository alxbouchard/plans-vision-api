# Test Data

This directory contains test fixtures for regression testing the Plans Vision API.

## Folder Structure

```
testdata/
├── README.md           # This file
├── consistent_set/     # 3 pages with consistent visual conventions
│   ├── page1.png
│   ├── page2.png
│   └── page3.png
├── contradiction_set/  # 2 pages with contradicting conventions
│   ├── page1.png
│   └── page2.png
└── synthetic/          # Programmatically generated test images
    └── *.png
```

## Test Sets

### consistent_set/ (Regression Test)

Contains 3 pages of construction plans with **consistent visual conventions**:
- Structural walls: thick black lines (2px)
- Partition walls: thin gray lines (1px)
- Doors: quarter-circle swing indicators
- Windows: parallel lines with hatch
- Dimensions: standard annotation style

**Expected Result**: Pipeline produces a STABLE guide with high confidence.

### contradiction_set/ (Rejection Test)

Contains 2 pages with **contradicting conventions**:
- Page 1: Doors shown as quarter-circle swings
- Page 2: Doors shown as rectangular cutouts (different convention)

**Expected Result**: Pipeline rejects guide due to contradiction (UNSTABLE).

## Important Notes

1. **No sensitive data**: All fixtures must be synthetic or anonymized.
   Never include actual client plans.

2. **PNG format**: All images must be valid PNG files.

3. **Reasonable size**: Keep images under 5MB each for fast tests.

4. **Documentation**: Each set should have a brief description of what
   conventions are present/violated.

## Creating New Fixtures

When adding new test sets:

1. Create a new subdirectory with a descriptive name
2. Add PNG images numbered `page1.png`, `page2.png`, etc.
3. Document the expected behavior in this README
4. Add corresponding tests in `tests/test_fixtures.py`
