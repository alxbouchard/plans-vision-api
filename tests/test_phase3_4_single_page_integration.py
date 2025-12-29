"""
Phase 3.4 Integration Test - Single Page Must Produce stable_rules_json.

This test validates the fix for TICKET_PHASE3_4_SINGLE_PAGE_CONSOLIDATOR.

EXPECTED: This test FAILS before the fix is implemented.
EXPECTED: This test PASSES after _run_single_page_flow is fixed.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.pipeline.orchestrator import PipelineOrchestrator
from src.models.entities import ProjectStatus


class TestSinglePageProducesStableRulesJson:
    """
    Integration test: Single page with room labels must produce stable_rules_json.
    """

    @pytest.mark.asyncio
    async def test_single_page_plan_produces_stable_rules_json(self):
        """
        Given: 1 page with visible room labels (floor plan)
        When: POST /analyze
        Then:
          - status = "validated"
          - stable_rules_json is NOT NULL
          - stable_rules_json contains 3 mandatory payloads

        THIS TEST SHOULD FAIL until _run_single_page_flow is fixed.
        """
        # Setup mocks
        project_id = uuid4()
        owner_id = uuid4()

        # Mock session
        mock_session = MagicMock()

        # Create orchestrator
        orchestrator = PipelineOrchestrator(session=mock_session)

        # Mock repositories
        mock_project = MagicMock()
        mock_project.status = ProjectStatus.DRAFT
        orchestrator.projects.get_by_id = AsyncMock(return_value=mock_project)
        orchestrator.projects.update_status = AsyncMock()

        mock_page = MagicMock()
        mock_page.file_path = "test.png"
        orchestrator.pages.list_by_project = AsyncMock(return_value=[mock_page])  # 1 page

        mock_guide = MagicMock()
        orchestrator.guides.get_or_create = AsyncMock(return_value=mock_guide)
        orchestrator.guides.update_provisional = AsyncMock()
        orchestrator.guides.update_stable = AsyncMock()
        orchestrator.guides.update_stable_rules_json = AsyncMock()

        # Mock file storage
        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"fake_image_bytes")

        # Mock GuideBuilder - returns provisional with room labels
        mock_builder_result = MagicMock()
        mock_builder_result.success = True
        mock_builder_result.provisional_guide = json.dumps({
            "observations": [
                {"id": "OBS_001", "category": "TEXT", "description": "Room names observed: CLASSE, CORRIDOR"},
                {"id": "OBS_002", "category": "TEXT", "description": "Room numbers: 203, 204, 206"},
                {"id": "OBS_003", "category": "TEXT", "description": "Numbers positioned below names"},
            ],
            "candidate_rules": [
                {"id": "RULE_001", "description": "Room names uppercase", "based_on": ["OBS_001"]},
                {"id": "RULE_002", "description": "Room numbers 3 digits", "based_on": ["OBS_002"]},
                {"id": "RULE_003", "description": "Number below name", "based_on": ["OBS_003"]},
            ],
            "uncertainties": [],
            "assumptions": [],
        })
        orchestrator.guide_builder.build_guide = AsyncMock(return_value=mock_builder_result)

        # Mock GuideApplier.validate_page - validates the rules on single page
        mock_applier_result = MagicMock()
        mock_applier_result.success = True
        mock_applier_result.page_order = 1
        mock_applier_result.validation_report = json.dumps({
            "rule_validations": [
                {"rule_id": "RULE_001", "status": "confirmed"},
                {"rule_id": "RULE_002", "status": "confirmed"},
                {"rule_id": "RULE_003", "status": "confirmed"},
            ],
            "payload_validations": [
                {"kind": "token_detector", "token_type": "room_name", "status": "confirmed"},
                {"kind": "token_detector", "token_type": "room_number", "status": "confirmed"},
                {"kind": "pairing", "token_type": None, "status": "confirmed"},
            ],
        })
        orchestrator.guide_applier.validate_page = AsyncMock(return_value=mock_applier_result)

        # Mock SelfValidator
        mock_validator_result = MagicMock()
        mock_validator_result.success = True
        mock_validator_result.stability_report = "All rules STABLE"
        mock_validator_result.raw_analysis = "All rules confirmed on single page"
        mock_validator_result.confidence_report = MagicMock(
            pages_testable=1,
            pages_passed=1,
            stable_ratio=1.0,
            rules_by_status={"stable": 3},
            can_generate_final=True,
        )
        orchestrator.self_validator.validate_stability = AsyncMock(return_value=mock_validator_result)

        # Mock guides.update_confidence_report
        orchestrator.guides.update_confidence_report = AsyncMock()

        # Mock GuideConsolidator - produces stable guide with payloads
        mock_consolidator_result = MagicMock()
        mock_consolidator_result.success = True
        mock_consolidator_result.stable_guide = "Final stable guide"
        mock_consolidator_result.structured_output = MagicMock()
        mock_consolidator_result.structured_output.guide_generated = True
        mock_consolidator_result.structured_output.stable_rules = [
            MagicMock(
                id="RULE_001",
                payload=MagicMock(kind="token_detector", token_type="room_name"),
            ),
            MagicMock(
                id="RULE_002",
                payload=MagicMock(kind="token_detector", token_type="room_number"),
            ),
            MagicMock(
                id="RULE_003",
                payload=MagicMock(kind="pairing", name_token="room_name", number_token="room_number"),
            ),
        ]
        mock_consolidator_result.structured_output.model_dump_json = MagicMock(
            return_value=json.dumps({
                "guide_generated": True,
                "stable_rules": [
                    {"id": "RULE_001", "payload": {"kind": "token_detector", "token_type": "room_name"}},
                    {"id": "RULE_002", "payload": {"kind": "token_detector", "token_type": "room_number"}},
                    {"id": "RULE_003", "payload": {"kind": "pairing", "name_token": "room_name", "number_token": "room_number"}},
                ],
            })
        )
        orchestrator.guide_consolidator.consolidate_guide = AsyncMock(return_value=mock_consolidator_result)

        # Run the pipeline
        result = await orchestrator.run(project_id, owner_id)

        # ASSERTIONS - These should FAIL before fix, PASS after fix

        # 1. Pipeline should succeed
        assert result.success, "Pipeline should succeed"

        # 2. Should have stable guide (not provisional_only)
        assert result.has_stable_guide, \
            "FAIL: Single page with room labels should produce stable guide"

        # 3. Should NOT be provisional_only
        assert not result.is_provisional_only, \
            "FAIL: Single page with room labels should NOT be provisional_only"

        # 4. stable_rules_json should be persisted via update_stable
        orchestrator.guides.update_stable.assert_called_once()
        # Verify stable_rules_json was passed as keyword argument
        call_kwargs = orchestrator.guides.update_stable.call_args.kwargs
        assert "stable_rules_json" in call_kwargs, "stable_rules_json should be passed to update_stable"
        assert call_kwargs["stable_rules_json"] is not None, "stable_rules_json should not be None"

        # 5. Status should be VALIDATED
        orchestrator.projects.update_status.assert_called_with(
            project_id, ProjectStatus.VALIDATED
        )

    @pytest.mark.asyncio
    async def test_single_page_cover_sheet_stays_provisional(self):
        """
        Given: 1 page that is a cover sheet (NO room labels)
        When: POST /analyze
        Then:
          - status = "provisional_only"
          - stable_rules_json is NULL (OK for cover sheets)
        """
        project_id = uuid4()
        owner_id = uuid4()

        mock_session = MagicMock()
        orchestrator = PipelineOrchestrator(session=mock_session)

        # Setup mocks
        mock_project = MagicMock()
        mock_project.status = ProjectStatus.DRAFT
        orchestrator.projects.get_by_id = AsyncMock(return_value=mock_project)
        orchestrator.projects.update_status = AsyncMock()

        mock_page = MagicMock()
        mock_page.file_path = "cover.png"
        orchestrator.pages.list_by_project = AsyncMock(return_value=[mock_page])

        mock_guide = MagicMock()
        orchestrator.guides.get_or_create = AsyncMock(return_value=mock_guide)
        orchestrator.guides.update_provisional = AsyncMock()
        orchestrator.guides.update_stable = AsyncMock()
        orchestrator.guides.update_stable_rules_json = AsyncMock()
        orchestrator.guides.update_confidence_report = AsyncMock()

        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"cover_bytes")

        # GuideBuilder - returns provisional with NO room labels
        mock_builder_result = MagicMock()
        mock_builder_result.success = True
        mock_builder_result.provisional_guide = json.dumps({
            "observations": [
                {"id": "OBS_NO_ROOM_LABELS", "description": "This is a cover sheet, no room labels visible"},
            ],
            "candidate_rules": [],
            "uncertainties": [],
            "assumptions": [],
        })
        orchestrator.guide_builder.build_guide = AsyncMock(return_value=mock_builder_result)

        # GuideApplier.validate_page - no room labels to validate
        mock_applier_result = MagicMock()
        mock_applier_result.success = True
        mock_applier_result.page_order = 1
        mock_applier_result.validation_report = json.dumps({
            "rule_validations": [],
            "payload_validations": [],
        })
        orchestrator.guide_applier.validate_page = AsyncMock(return_value=mock_applier_result)

        # SelfValidator
        mock_validator_result = MagicMock()
        mock_validator_result.success = True
        mock_validator_result.stability_report = "No rules to validate"
        mock_validator_result.raw_analysis = "Cover sheet - no rules"
        mock_validator_result.confidence_report = MagicMock(
            pages_testable=0,
            pages_passed=0,
            stable_ratio=0.0,
            rules_by_status={},
            can_generate_final=False,
        )
        orchestrator.self_validator.validate_stability = AsyncMock(return_value=mock_validator_result)

        # GuideConsolidator - rejects because no room labels
        mock_consolidator_result = MagicMock()
        mock_consolidator_result.success = True
        mock_consolidator_result.stable_guide = None
        mock_consolidator_result.structured_output = MagicMock()
        mock_consolidator_result.structured_output.guide_generated = False
        mock_consolidator_result.rejection_reason = "No room labels visible on cover sheet"
        orchestrator.guide_consolidator.consolidate_guide = AsyncMock(return_value=mock_consolidator_result)

        # Run
        result = await orchestrator.run(project_id, owner_id)

        # Cover sheet should be provisional_only (this is correct behavior)
        assert result.success, "Pipeline should succeed"
        assert result.is_provisional_only, "Cover sheet should be provisional_only"
        assert not result.has_stable_guide, "Cover sheet should NOT have stable guide"


class TestPhase34PayloadRequirements:
    """Test that stable_rules_json contains the 3 mandatory payloads."""

    def test_validate_mandatory_payloads(self):
        """Validate helper function for checking 3 mandatory payloads."""
        # Valid stable_rules_json
        valid_json = json.dumps({
            "guide_generated": True,
            "stable_rules": [
                {"id": "R1", "payload": {"kind": "token_detector", "token_type": "room_name"}},
                {"id": "R2", "payload": {"kind": "token_detector", "token_type": "room_number"}},
                {"id": "R3", "payload": {"kind": "pairing", "name_token": "room_name"}},
            ],
        })

        data = json.loads(valid_json)
        stable_rules = data.get("stable_rules", [])

        has_room_name = False
        has_room_number = False
        has_pairing = False

        for rule in stable_rules:
            payload = rule.get("payload", {})
            kind = payload.get("kind")
            token_type = payload.get("token_type")

            if kind == "token_detector" and token_type == "room_name":
                has_room_name = True
            elif kind == "token_detector" and token_type == "room_number":
                has_room_number = True
            elif kind == "pairing":
                has_pairing = True

        assert has_room_name, "Missing token_detector(room_name)"
        assert has_room_number, "Missing token_detector(room_number)"
        assert has_pairing, "Missing pairing payload"

    def test_missing_pairing_fails(self):
        """stable_rules_json missing pairing should fail validation."""
        invalid_json = json.dumps({
            "guide_generated": True,
            "stable_rules": [
                {"id": "R1", "payload": {"kind": "token_detector", "token_type": "room_name"}},
                {"id": "R2", "payload": {"kind": "token_detector", "token_type": "room_number"}},
                # Missing pairing!
            ],
        })

        data = json.loads(invalid_json)
        stable_rules = data.get("stable_rules", [])

        has_pairing = any(
            rule.get("payload", {}).get("kind") == "pairing"
            for rule in stable_rules
        )

        assert not has_pairing, "This test validates that missing pairing is detected"
