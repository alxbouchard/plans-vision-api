# TICKET: Step A — PDF Storage Association

**Status: PR1 DONE, PR2 PENDING**
**Created: 2025-12-29**
**Updated: 2025-12-29**
**Depends on: Steps B/C/D/E (COMPLETE)**

## Objective

Enable the API to use tokens-first extraction automatically when a PDF is provided,
without breaking the existing PNG upload flow.

## Constraints (Non-Negotiable)

1. **No DB schema change without migration + tests**
2. **Backward compatible**: If a project has no PDF, behavior identical to before
3. **No hardcode**: All semantic refinement stays in the guide (exclude payloads)
4. **No new RuleKind**: We stay with `token_detector`, `pairing`, `exclude`

## Options

### Option 1: Add fields to Page entity (Recommended)

Add `pdf_path` and `pdf_page_index` to the existing Page table.

**Pros:**
- Simple schema change
- Direct association per page
- No new tables

**Cons:**
- All pages share the same PDF path (redundant storage)
- Migration required for existing DBs

**Schema change:**
```sql
ALTER TABLE pages ADD COLUMN pdf_path VARCHAR(512) NULL;
ALTER TABLE pages ADD COLUMN pdf_page_index INTEGER NULL;
```

### Option 2: New PDFSource table

Create a separate table linking projects to PDF files.

```sql
CREATE TABLE pdf_sources (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) REFERENCES projects(id),
    file_path VARCHAR(512) NOT NULL,
    page_count INTEGER NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE pages ADD COLUMN pdf_source_id VARCHAR(36) REFERENCES pdf_sources(id) NULL;
ALTER TABLE pages ADD COLUMN pdf_page_index INTEGER NULL;
```

**Pros:**
- Cleaner data model
- PDF metadata stored once
- Easier to support multiple PDFs per project later

**Cons:**
- More complex migration
- New table to maintain

### Option 3: Use existing PDFMasterTable

The `pdf_masters` table already exists in the V3 schema. We could link pages to it.

**Schema change:**
```sql
ALTER TABLE pages ADD COLUMN pdf_master_id VARCHAR(36) REFERENCES pdf_masters(id) NULL;
ALTER TABLE pages ADD COLUMN pdf_page_index INTEGER NULL;
```

**Pros:**
- Reuses existing infrastructure
- Already has fingerprint/page_count

**Cons:**
- PDFMasterTable is for V3 render pipeline
- May conflate two different use cases

---

## Recommendation: Option 1 (Simple fields on Page)

For Phase 3.5, keep it simple. Add fields directly to Page.

## Livrables

### A1: This Ticket ✓

### A2: Migration (PR1)

**Files to modify:**
- `src/models/entities.py` - Add `pdf_path`, `pdf_page_index` to Page
- `src/storage/database.py` - Add columns to PageTable
- `scripts/migrate_add_pdf_fields.py` - Migration script (new)

**Migration script:**
```python
# scripts/migrate_add_pdf_fields.py
import sqlite3
import sys

def migrate(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(pages)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'pdf_path' not in columns:
        cursor.execute("ALTER TABLE pages ADD COLUMN pdf_path VARCHAR(512) NULL")

    if 'pdf_page_index' not in columns:
        cursor.execute("ALTER TABLE pages ADD COLUMN pdf_page_index INTEGER NULL")

    conn.commit()
    conn.close()
    print(f"Migration complete: {db_path}")

if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else "plans_vision.db")
```

### A3: PDF Upload Endpoint (PR2)

**New endpoint:** `POST /projects/{project_id}/pdf`

**Behavior:**
1. Accept PDF file upload
2. Store PDF in file storage
3. Extract pages as PNG using PyMuPDF
4. Create Page entries with `pdf_path` and `pdf_page_index` set
5. Return list of created pages

**Files to create/modify:**
- `src/api/routes/pdf.py` - New file: PDF upload endpoint
- `src/storage/file_storage.py` - Add `save_pdf()` method
- `src/api/routes/__init__.py` - Register new router

**Alternative:** Optional parameter on existing page upload
- Less intrusive but doesn't auto-extract pages

### A4: Non-Regression Test

**Test:** Upload PNG only → analyze/extract works as before

```python
# tests/test_non_regression_png_only.py

@pytest.mark.asyncio
async def test_png_only_workflow_unchanged():
    """PNG-only projects work exactly as before Step A."""
    # 1. Create project
    # 2. Upload PNG pages (no PDF)
    # 3. POST /analyze
    # 4. Assert: status = validated or provisional_only
    # 5. Assert: Pages have pdf_path = NULL
    # 6. POST /extract
    # 7. Assert: extraction works (rooms_emitted >= 0)
```

### A5: Tokens-First Test

**Test:** Upload PDF → analyze produces stable_rules_json

```python
# tests/test_tokens_first_pdf_upload.py

@pytest.mark.asyncio
async def test_pdf_upload_produces_stable_rules():
    """PDF upload enables tokens-first and produces valid guide."""
    # 1. Create project
    # 2. POST /projects/{id}/pdf with Addenda PDF
    # 3. Assert: Pages created with pdf_path and pdf_page_index
    # 4. POST /analyze
    # 5. Assert: token_summary was used (check logs)
    # 6. Assert: status = validated
    # 7. Assert: stable_rules_json contains 3+ payloads
```

---

## Stop Rule

If Step A risks breaking existing functionality, split into two PRs:

### PR1: Migration + Compat + Tests
- Add columns with NULL default
- Migration script
- Non-regression test (A4)
- No behavioral change yet

### PR2: PDF Endpoint + Integration
- New PDF upload endpoint
- Orchestrator uses pdf_path from Page entity
- Tokens-first integration test (A5)

---

## Checklist

- [x] A1: Ticket created (this file)
- [x] A2: Migration script + schema change (PR1)
- [ ] A3: PDF upload endpoint (PR2)
- [x] A4: Non-regression test passing (PR1)
- [ ] A5: Tokens-first test passing (PR2)
- [x] All existing tests still passing (280 pass, 4 skip)

## Migration Notes

**Current State (PR1):**
- Standalone SQLite migration script: `scripts/migrations/001_add_pdf_source_fields.py`
- Fields: `source_pdf_path` (TEXT), `source_pdf_page_index` (INTEGER)
- Idempotent: safe to run multiple times

**Future (PR2/PR3):**
- Port to Alembic if production deployment requires version tracking
- Consider adding `pdf_masters` FK if V3 render pipeline needs integration

## Success Criteria

1. `POST /projects/{id}/pages` (PNG) works exactly as before
2. `POST /projects/{id}/pdf` creates pages with PDF association
3. `/analyze` uses tokens-first when pdf_path is set
4. Addenda page 1 produces stable_rules_json with 3+ payloads
