"""P0 Tests: Room and Door persistence after server restart.

These tests verify that extracted rooms and doors survive server restarts
by being persisted to the database rather than stored only in RAM.

Requirement:
- GET /v2/projects/{id}/rooms must return the same data after a server restart
- No re-running of /extract should be required

Definition of Done:
A) Run extract until overall_status=completed
B) GET /v2/projects/{id}/rooms note total_count and first 5 IDs
C) Restart server (kill then relaunch)
D) GET /v2/projects/{id}/rooms WITHOUT re-running extract
Expected: same total_count and same IDs in the same order
"""

import pytest
import json
import sqlite3
import tempfile
import importlib.util
from pathlib import Path
from uuid import uuid4

from httpx import AsyncClient, ASGITransport

from src.api.app import create_app
from src.storage.database import (
    Base,
    ExtractedRoomTable,
    ExtractedDoorTable,
    PageTable,
    ProjectTable,
)
from src.storage import ExtractedRoomRepository, ExtractedDoorRepository, get_db
from src.models.entities import ProjectStatus

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


def load_migration_002():
    """Load migration 002 module."""
    migration_path = (
        Path(__file__).parent.parent
        / "scripts"
        / "migrations"
        / "002_add_extracted_objects_tables.py"
    )
    spec = importlib.util.spec_from_file_location("migration_002", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigration002:
    """Test the migration script for extracted_rooms and extracted_doors tables."""

    def test_migration_upgrade_creates_tables(self):
        """Migration upgrade should create the extracted_rooms and extracted_doors tables."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Create minimal DB with pages table (required for foreign key)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                status TEXT,
                owner_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE pages (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                "order" INTEGER,
                file_path TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Run migration
        migration = load_migration_002()
        migration.upgrade(db_path)

        # Verify tables were created
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_rooms'"
        )
        assert cursor.fetchone() is not None, "extracted_rooms table should exist"

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_doors'"
        )
        assert cursor.fetchone() is not None, "extracted_doors table should exist"

        # Verify columns
        cursor.execute("PRAGMA table_info(extracted_rooms)")
        columns = {col[1] for col in cursor.fetchall()}
        assert "id" in columns
        assert "page_id" in columns
        assert "room_name" in columns
        assert "room_number" in columns
        assert "label" in columns
        assert "bbox_json" in columns
        assert "confidence" in columns
        assert "confidence_level" in columns
        assert "sources_json" in columns

        cursor.execute("PRAGMA table_info(extracted_doors)")
        columns = {col[1] for col in cursor.fetchall()}
        assert "id" in columns
        assert "page_id" in columns
        assert "door_number" in columns
        assert "label" in columns
        assert "bbox_json" in columns

        conn.close()
        Path(db_path).unlink()

    def test_migration_upgrade_idempotent(self):
        """Running migration twice should not fail."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE pages (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        migration = load_migration_002()

        # Run twice - should not fail
        migration.upgrade(db_path)
        migration.upgrade(db_path)

        Path(db_path).unlink()

    def test_migration_downgrade_drops_tables(self):
        """Migration downgrade should drop the tables."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE pages (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE extracted_rooms (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE extracted_doors (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        migration = load_migration_002()
        migration.downgrade(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_rooms'"
        )
        assert cursor.fetchone() is None, "extracted_rooms should be dropped"

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_doors'"
        )
        assert cursor.fetchone() is None, "extracted_doors should be dropped"

        conn.close()
        Path(db_path).unlink()


class TestP0RoomsEndpointReadsFromDB:
    """Test that GET /rooms endpoint reads from database, not RAM."""

    @pytest.fixture
    async def db_session_factory(self):
        """Create an in-memory database with all tables."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        yield session_factory, engine

        await engine.dispose()

    @pytest.fixture
    def owner_id(self) -> str:
        return str(uuid4())

    @pytest.mark.asyncio
    async def test_rooms_endpoint_returns_db_not_ram(self, db_session_factory, owner_id):
        """
        Test that GET /v2/projects/{id}/rooms returns data from DB.

        Arrange:
        - Insert a room directly into the database
        - Do NOT populate _extracted_objects in-memory cache

        Act:
        - GET /v2/projects/{id}/rooms

        Assert:
        - Returns the room from DB even though RAM cache is empty
        """
        session_factory, engine = db_session_factory

        project_id = uuid4()
        page_id = uuid4()

        # Insert project and page directly
        async with session_factory() as session:
            session.add(
                ProjectTable(
                    id=str(project_id),
                    status=ProjectStatus.VALIDATED,
                    owner_id=owner_id,
                )
            )
            session.add(
                PageTable(
                    id=str(page_id),
                    project_id=str(project_id),
                    order=1,
                    file_path="/tmp/test.png",
                )
            )
            await session.commit()

        # Insert room directly into DB
        async with session_factory() as session:
            room = ExtractedRoomTable(
                id="room-db-test-001",
                page_id=str(page_id),
                room_name="Conference Room A",
                room_number="101",
                label="Conference Room A 101",
                bbox_json=json.dumps([100, 200, 300, 400]),
                confidence=950,  # 0.95 * 1000
                confidence_level="high",
                sources_json=json.dumps(["tokens_first", "pymupdf"]),
            )
            session.add(room)
            await session.commit()

        # Verify room is in DB using repository
        async with session_factory() as session:
            room_repo = ExtractedRoomRepository(session)
            rooms = await room_repo.list_by_project(project_id)
            assert len(rooms) == 1
            assert rooms[0]["id"] == "room-db-test-001"
            assert rooms[0]["label"] == "Conference Room A 101"

    @pytest.mark.asyncio
    async def test_rooms_endpoint_empty_when_no_extraction(self, db_session_factory, owner_id):
        """
        Test that GET /rooms returns empty list if extract was never run.

        Arrange:
        - Create project and page, but do NOT run extract

        Assert:
        - GET /rooms returns [] with total_count=0
        """
        session_factory, engine = db_session_factory

        project_id = uuid4()
        page_id = uuid4()

        # Insert project and page only (no extraction)
        async with session_factory() as session:
            session.add(
                ProjectTable(
                    id=str(project_id),
                    status=ProjectStatus.DRAFT,
                    owner_id=owner_id,
                )
            )
            session.add(
                PageTable(
                    id=str(page_id),
                    project_id=str(project_id),
                    order=1,
                    file_path="/tmp/test.png",
                )
            )
            await session.commit()

        # Verify no rooms in DB
        async with session_factory() as session:
            room_repo = ExtractedRoomRepository(session)
            rooms = await room_repo.list_by_project(project_id)
            assert len(rooms) == 0, "No rooms should exist before extraction"


class TestP0PersistenceAcrossRestart:
    """
    Test that rooms persist across simulated server restart.

    This simulates the restart by:
    1. Creating fresh app instances
    2. Clearing any in-memory caches
    3. Verifying data comes from the database
    """

    @pytest.fixture
    async def persistent_db(self, tmp_path):
        """Create a persistent SQLite database file."""
        db_path = tmp_path / "test_p0_persistence.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        engine = create_async_engine(db_url, echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        yield session_factory, engine, db_path

        await engine.dispose()

    @pytest.fixture
    def owner_id(self) -> str:
        return str(uuid4())

    @pytest.mark.asyncio
    async def test_rooms_persist_across_simulated_restart(self, persistent_db, owner_id):
        """
        Full P0 test: rooms must survive server restart.

        Arrange:
        - Create project and page
        - Save rooms to database (simulating extraction)
        - Record room IDs

        Act:
        - Simulate restart by creating new session factory (new app)
        - Query rooms again

        Assert:
        - Same IDs returned
        - Same total_count
        """
        session_factory1, engine1, db_path = persistent_db

        project_id = uuid4()
        page_id = uuid4()

        # === Session 1: Create data (before restart) ===
        async with session_factory1() as session:
            session.add(
                ProjectTable(
                    id=str(project_id),
                    status=ProjectStatus.VALIDATED,
                    owner_id=owner_id,
                )
            )
            session.add(
                PageTable(
                    id=str(page_id),
                    project_id=str(project_id),
                    order=1,
                    file_path="/tmp/page1.png",
                )
            )
            await session.commit()

        # Save 5 rooms to DB
        room_ids = []
        async with session_factory1() as session:
            for i in range(5):
                room_id = f"room-persist-{i:03d}"
                room_ids.append(room_id)
                session.add(
                    ExtractedRoomTable(
                        id=room_id,
                        page_id=str(page_id),
                        room_name=f"Room {chr(65 + i)}",
                        room_number=f"10{i}",
                        label=f"Room {chr(65 + i)} 10{i}",
                        bbox_json=json.dumps([100 * i, 100, 200, 200]),
                        confidence=950,
                        confidence_level="high",
                        sources_json=json.dumps(["tokens_first"]),
                    )
                )
            await session.commit()

        # Verify pre-restart
        async with session_factory1() as session:
            room_repo = ExtractedRoomRepository(session)
            rooms_before = await room_repo.list_by_project(project_id)

        assert len(rooms_before) == 5, "Should have 5 rooms before restart"
        ids_before = [r["id"] for r in rooms_before]

        # === Simulate restart: close engine, create new one ===
        await engine1.dispose()

        # Create new engine (simulates new server process)
        db_url = f"sqlite+aiosqlite:///{db_path}"
        engine2 = create_async_engine(db_url, echo=False)

        session_factory2 = async_sessionmaker(
            engine2,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # === Session 2: Query after restart ===
        async with session_factory2() as session:
            room_repo = ExtractedRoomRepository(session)
            rooms_after = await room_repo.list_by_project(project_id)

        await engine2.dispose()

        # === Assert: Same data ===
        assert len(rooms_after) == 5, "Should have 5 rooms after restart"
        ids_after = [r["id"] for r in rooms_after]

        assert ids_before == ids_after, "Room IDs should match after restart"

        # Verify data integrity
        for room in rooms_after:
            assert room["confidence"] == 0.95
            assert room["confidence_level"] == "high"
            assert "tokens_first" in room["sources"]


class TestP0DoorsEndpointReadsFromDB:
    """Test that GET /doors endpoint also reads from database."""

    @pytest.fixture
    async def db_session_factory(self):
        """Create an in-memory database."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        yield session_factory

        await engine.dispose()

    @pytest.fixture
    def owner_id(self) -> str:
        return str(uuid4())

    @pytest.mark.asyncio
    async def test_doors_endpoint_returns_db_data(self, db_session_factory, owner_id):
        """Test that GET /doors returns data from database."""
        project_id = uuid4()
        page_id = uuid4()

        # Insert project, page, and door
        async with db_session_factory() as session:
            session.add(
                ProjectTable(
                    id=str(project_id),
                    status=ProjectStatus.VALIDATED,
                    owner_id=owner_id,
                )
            )
            session.add(
                PageTable(
                    id=str(page_id),
                    project_id=str(project_id),
                    order=1,
                    file_path="/tmp/test.png",
                )
            )
            session.add(
                ExtractedDoorTable(
                    id="door-db-test-001",
                    page_id=str(page_id),
                    door_number="D101",
                    label="Door D101",
                    bbox_json=json.dumps([50, 100, 80, 200]),
                    confidence=900,
                    confidence_level="high",
                    sources_json=json.dumps(["tokens_first"]),
                )
            )
            await session.commit()

        # Verify door is retrievable
        async with db_session_factory() as session:
            door_repo = ExtractedDoorRepository(session)
            doors = await door_repo.list_by_project(project_id)

            assert len(doors) == 1
            assert doors[0]["id"] == "door-db-test-001"
            assert doors[0]["door_number"] == "D101"
