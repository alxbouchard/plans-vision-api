#!/usr/bin/env python3
"""Migration 002: Add extracted_rooms and extracted_doors tables.

Phase 3.7 P0 - Persistence of extracted objects.

Creates:
- extracted_rooms: Persisted room extraction results
- extracted_doors: Persisted door extraction results

These tables enable persistence of extraction results across server restarts.
Prior to this migration, extracted objects were only stored in memory.

Usage:
    python scripts/migrations/002_add_extracted_objects_tables.py [upgrade|downgrade] [db_path]

    upgrade   - Create the new tables (default)
    downgrade - Drop the tables (destructive!)
    db_path   - Path to SQLite database (default: plans_vision.db)
"""

import sqlite3
import sys
from pathlib import Path


def check_table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def upgrade(db_path: str) -> None:
    """Create extracted_rooms and extracted_doors tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create extracted_rooms table
        if check_table_exists(cursor, "extracted_rooms"):
            print("Table 'extracted_rooms' already exists")
        else:
            cursor.execute("""
                CREATE TABLE extracted_rooms (
                    id VARCHAR(64) PRIMARY KEY,
                    page_id VARCHAR(36) NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
                    room_name VARCHAR(256),
                    room_number VARCHAR(64),
                    label VARCHAR(512) NOT NULL,
                    bbox_json TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    confidence_level VARCHAR(20) NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX ix_extracted_rooms_page_id ON extracted_rooms(page_id)")
            print("Created table 'extracted_rooms' with index")

        # Create extracted_doors table
        if check_table_exists(cursor, "extracted_doors"):
            print("Table 'extracted_doors' already exists")
        else:
            cursor.execute("""
                CREATE TABLE extracted_doors (
                    id VARCHAR(64) PRIMARY KEY,
                    page_id VARCHAR(36) NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
                    door_number VARCHAR(64),
                    label VARCHAR(512) NOT NULL,
                    bbox_json TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    confidence_level VARCHAR(20) NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX ix_extracted_doors_page_id ON extracted_doors(page_id)")
            print("Created table 'extracted_doors' with index")

        conn.commit()
        print(f"Migration 002 upgrade complete: {db_path}")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def downgrade(db_path: str) -> None:
    """Drop extracted_rooms and extracted_doors tables.

    WARNING: This is destructive! All extracted object data will be lost.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        if check_table_exists(cursor, "extracted_rooms"):
            cursor.execute("DROP TABLE extracted_rooms")
            print("Dropped table 'extracted_rooms'")
        else:
            print("Table 'extracted_rooms' does not exist")

        if check_table_exists(cursor, "extracted_doors"):
            cursor.execute("DROP TABLE extracted_doors")
            print("Dropped table 'extracted_doors'")
        else:
            print("Table 'extracted_doors' does not exist")

        conn.commit()
        print(f"Migration 002 downgrade complete: {db_path}")

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
        print("WARNING: Downgrade will DELETE all extracted rooms and doors!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            downgrade(db_path)
        else:
            print("Downgrade cancelled")


if __name__ == "__main__":
    main()
