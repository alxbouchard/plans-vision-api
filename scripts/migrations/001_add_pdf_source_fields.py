#!/usr/bin/env python3
"""Migration 001: Add PDF source fields to pages table.

Phase 3.5 - Tokens-first extraction support.

Adds:
- source_pdf_path: Path to source PDF file (nullable)
- source_pdf_page_index: Page index in PDF, 0-indexed (nullable)

These fields enable PyMuPDF token extraction when a PDF source is available.
If NULL, the system falls back to Vision-based extraction (unchanged behavior).

Usage:
    python scripts/migrations/001_add_pdf_source_fields.py [upgrade|downgrade] [db_path]

    upgrade   - Add the new columns (default)
    downgrade - Remove the columns (destructive!)
    db_path   - Path to SQLite database (default: plans_vision.db)
"""

import sqlite3
import sys
from pathlib import Path


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    return column in columns


def upgrade(db_path: str) -> None:
    """Add source_pdf_path and source_pdf_page_index columns."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        if check_column_exists(cursor, "pages", "source_pdf_path"):
            print(f"Column 'source_pdf_path' already exists in {db_path}")
        else:
            cursor.execute(
                "ALTER TABLE pages ADD COLUMN source_pdf_path TEXT NULL"
            )
            print(f"Added column 'source_pdf_path' to pages table")

        if check_column_exists(cursor, "pages", "source_pdf_page_index"):
            print(f"Column 'source_pdf_page_index' already exists in {db_path}")
        else:
            cursor.execute(
                "ALTER TABLE pages ADD COLUMN source_pdf_page_index INTEGER NULL"
            )
            print(f"Added column 'source_pdf_page_index' to pages table")

        conn.commit()
        print(f"Migration 001 upgrade complete: {db_path}")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def downgrade(db_path: str) -> None:
    """Remove source_pdf_path and source_pdf_page_index columns.

    WARNING: This is destructive! SQLite doesn't support DROP COLUMN directly
    in older versions, so we recreate the table.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check SQLite version for DROP COLUMN support (3.35.0+)
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        major, minor, patch = map(int, version.split('.'))

        if (major, minor) >= (3, 35):
            # SQLite 3.35+ supports DROP COLUMN
            if check_column_exists(cursor, "pages", "source_pdf_path"):
                cursor.execute("ALTER TABLE pages DROP COLUMN source_pdf_path")
                print("Dropped column 'source_pdf_path'")

            if check_column_exists(cursor, "pages", "source_pdf_page_index"):
                cursor.execute("ALTER TABLE pages DROP COLUMN source_pdf_page_index")
                print("Dropped column 'source_pdf_page_index'")
        else:
            # Older SQLite: recreate table without the columns
            print(f"SQLite {version} doesn't support DROP COLUMN, recreating table...")

            # Get existing columns (excluding the ones to drop)
            cursor.execute("PRAGMA table_info(pages)")
            columns = [
                col[1] for col in cursor.fetchall()
                if col[1] not in ("source_pdf_path", "source_pdf_page_index")
            ]

            if not columns:
                print("No columns to keep, skipping downgrade")
                return

            columns_str = ", ".join(columns)

            # Recreate without the new columns
            cursor.execute(f"""
                CREATE TABLE pages_backup AS
                SELECT {columns_str} FROM pages
            """)
            cursor.execute("DROP TABLE pages")
            cursor.execute(f"""
                CREATE TABLE pages (
                    id VARCHAR(36) PRIMARY KEY,
                    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
                    "order" INTEGER,
                    file_path VARCHAR(512),
                    created_at DATETIME,
                    image_width INTEGER,
                    image_height INTEGER,
                    image_sha256 VARCHAR(64),
                    byte_size INTEGER,
                    page_type VARCHAR(20),
                    classification_confidence INTEGER,
                    classified_at DATETIME
                )
            """)
            cursor.execute(f"""
                INSERT INTO pages ({columns_str})
                SELECT {columns_str} FROM pages_backup
            """)
            cursor.execute("DROP TABLE pages_backup")
            cursor.execute("CREATE INDEX ix_pages_project_id ON pages(project_id)")

            print("Recreated pages table without PDF source columns")

        conn.commit()
        print(f"Migration 001 downgrade complete: {db_path}")

    except Exception as e:
        conn.rollback()
        print(f"Downgrade failed: {e}")
        raise
    finally:
        conn.close()


def main():
    # Parse arguments
    action = "upgrade"
    db_path = "plans_vision.db"

    args = sys.argv[1:]
    if args:
        if args[0] in ("upgrade", "downgrade"):
            action = args[0]
            if len(args) > 1:
                db_path = args[1]
        else:
            db_path = args[0]

    # Check database exists
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        print("Creating new database with init_database() instead.")
        sys.exit(1)

    # Run migration
    if action == "upgrade":
        upgrade(db_path)
    else:
        print("WARNING: Downgrade will remove PDF source data!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            downgrade(db_path)
        else:
            print("Downgrade cancelled")


if __name__ == "__main__":
    main()
