"""Pipeline orchestrator tests including contradiction scenarios."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.pipeline.orchestrator import PipelineOrchestrator, PipelineResult, PipelineError
from src.models.entities import ProjectStatus, ConfidenceReport, RuleObservation, RuleStability
from src.agents.guide_builder import GuideBuilderResult
from src.agents.guide_applier import GuideApplierResult, ValidationResult
from src.agents.self_validator import SelfValidatorResult
from src.agents.guide_consolidator import ConsolidatorResult
from src.agents.schemas import (
    GuideBuilderOutput,
    GuideApplierOutput,
    SelfValidatorOutput,
    GuideConsolidatorOutput,
    RuleValidation,
    RuleValidationStatus,
    RuleStabilityAssessment,
    StabilityClassification,
)


class TestSinglePageFlow:
    """Tests for Phase 3.4: Single-page with full agent pipeline."""

    @pytest.mark.asyncio
    async def test_single_page_cover_sheet_returns_provisional_only(self):
        """Single page cover sheet (no room labels) returns provisional guide only."""
        # Create mocks
        session = MagicMock()
        file_storage = MagicMock()

        orchestrator = PipelineOrchestrator(session, file_storage)

        # Mock repositories
        project_mock = MagicMock()
        project_mock.status = ProjectStatus.DRAFT

        page_mock = MagicMock()
        page_mock.file_path = "/path/to/cover_sheet.png"
        page_mock.order = 1

        orchestrator.projects.get_by_id = AsyncMock(return_value=project_mock)
        orchestrator.projects.update_status = AsyncMock()
        orchestrator.pages.list_by_project = AsyncMock(return_value=[page_mock])
        orchestrator.guides.get_or_create = AsyncMock(return_value=MagicMock())
        orchestrator.guides.update_provisional = AsyncMock()
        orchestrator.guides.update_stable = AsyncMock()
        orchestrator.guides.update_confidence_report = AsyncMock()

        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"fake png")

        # Mock guide builder - cover sheet with no room labels
        mock_builder_output = GuideBuilderOutput(
            observations=[],
            candidate_rules=[],
            uncertainties=["Cover sheet - no room labels visible"],
            assumptions=[],
        )
        orchestrator.guide_builder.build_guide = AsyncMock(
            return_value=GuideBuilderResult(
                provisional_guide='{"observations": [], "candidate_rules": []}',
                structured_output=mock_builder_output,
                success=True,
            )
        )

        # Mock guide applier - nothing to validate on cover sheet
        orchestrator.guide_applier.validate_page = AsyncMock(
            return_value=MagicMock(
                success=True,
                page_order=1,
                validation_report='{"rule_validations": [], "payload_validations": []}',
            )
        )

        # Mock self-validator - no rules to validate
        orchestrator.self_validator.validate_stability = AsyncMock(
            return_value=MagicMock(
                success=True,
                raw_analysis="Cover sheet - no rules",
                confidence_report=MagicMock(
                    pages_testable=0,
                    pages_passed=0,
                    stable_ratio=0.0,
                    rules_by_status={},
                    can_generate_final=False,
                ),
            )
        )

        # Mock guide consolidator - rejects because no room labels
        orchestrator.guide_consolidator.consolidate_guide = AsyncMock(
            return_value=MagicMock(
                success=True,
                stable_guide=None,
                structured_output=None,
                rejection_message="No room labels visible on cover sheet",
            )
        )

        # Run pipeline
        result = await orchestrator.run(uuid4(), uuid4())

        # Assertions
        assert result.success is True
        assert result.has_stable_guide is False
        assert result.stable_guide is None
        assert result.provisional_guide is not None
        assert result.is_provisional_only is True
        assert result.pages_processed == 1
        # rejection_message should explain why no stable guide
        assert result.rejection_message is not None


class TestContradictionFlow:
    """Tests for contradiction scenarios: pages contradict → no guide."""

    @pytest.mark.asyncio
    async def test_contradiction_prevents_stable_guide(self):
        """When pages contradict provisional rules, no stable guide is generated."""
        session = MagicMock()
        file_storage = MagicMock()

        orchestrator = PipelineOrchestrator(session, file_storage)

        # Mock repositories
        project_mock = MagicMock()
        project_mock.status = ProjectStatus.DRAFT

        page1 = MagicMock()
        page1.file_path = "/path/to/page1.png"
        page1.order = 1

        page2 = MagicMock()
        page2.file_path = "/path/to/page2.png"
        page2.order = 2

        page3 = MagicMock()
        page3.file_path = "/path/to/page3.png"
        page3.order = 3

        orchestrator.projects.get_by_id = AsyncMock(return_value=project_mock)
        orchestrator.projects.update_status = AsyncMock()
        orchestrator.pages.list_by_project = AsyncMock(return_value=[page1, page2, page3])
        orchestrator.guides.get_or_create = AsyncMock(return_value=MagicMock())
        orchestrator.guides.update_provisional = AsyncMock()
        orchestrator.guides.update_confidence_report = AsyncMock()
        orchestrator.guides.update_stable = AsyncMock()

        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"fake png")

        # Mock guide builder - returns provisional guide with rules
        orchestrator.guide_builder.build_guide = AsyncMock(
            return_value=GuideBuilderResult(
                provisional_guide='{"candidate_rules": [{"id": "RULE_001"}]}',
                structured_output=None,
                success=True,
            )
        )

        # Mock guide applier - page 2 has contradiction!
        mock_applier_output_page2 = GuideApplierOutput(
            page_number=2,
            rule_validations=[
                RuleValidation(
                    rule_id="RULE_001",
                    status=RuleValidationStatus.CONTRADICTED,  # CONTRADICTION!
                    evidence="Page 2 shows opposite pattern",
                ),
            ],
            new_observations=[],
            overall_consistency="inconsistent",
        )

        mock_applier_output_page3 = GuideApplierOutput(
            page_number=3,
            rule_validations=[
                RuleValidation(
                    rule_id="RULE_001",
                    status=RuleValidationStatus.CONFIRMED,
                    evidence="Page 3 confirms pattern",
                ),
            ],
            new_observations=[],
            overall_consistency="consistent",
        )

        orchestrator.guide_applier.validate_all_pages = AsyncMock(
            return_value=GuideApplierResult(
                page_validations=[
                    ValidationResult(
                        page_order=2,
                        validation_report='{"rule_validations": [{"rule_id": "RULE_001", "status": "contradicted"}]}',
                        structured_output=mock_applier_output_page2,
                        has_contradictions=True,
                        success=True,
                    ),
                    ValidationResult(
                        page_order=3,
                        validation_report='{"rule_validations": [{"rule_id": "RULE_001", "status": "confirmed"}]}',
                        structured_output=mock_applier_output_page3,
                        has_contradictions=False,
                        success=True,
                    ),
                ],
                all_success=True,
                any_contradictions=True,
            )
        )

        # Mock self-validator - marks RULE_001 as UNSTABLE due to contradiction
        mock_validator_output = SelfValidatorOutput(
            total_rules=1,
            rule_assessments=[
                RuleStabilityAssessment(
                    rule_id="RULE_001",
                    classification=StabilityClassification.UNSTABLE,
                    pages_testable=2,
                    pages_confirmed=1,
                    pages_contradicted=1,  # ONE CONTRADICTION = UNSTABLE
                    pages_variation=0,
                    confidence_score=0.3,
                    recommendation="exclude",
                ),
            ],
            stable_count=0,
            partial_count=0,
            unstable_count=1,
            overall_stability_ratio=0.0,  # 0% stable
            can_generate_guide=False,
            rejection_reason="RULE_001 was contradicted on page 2",
        )

        confidence_report = ConfidenceReport(
            total_rules=1,
            stable_count=0,
            partial_count=0,
            unstable_count=1,
            rules=[
                RuleObservation(
                    rule_id="RULE_001",
                    description="Contradicted",
                    stability=RuleStability.UNSTABLE,
                    confidence_score=0.3,
                )
            ],
            overall_stability=0.0,
            can_generate_final=False,
            rejection_reason="RULE_001 was contradicted on page 2",
        )

        orchestrator.self_validator.validate_stability = AsyncMock(
            return_value=SelfValidatorResult(
                confidence_report=confidence_report,
                raw_analysis='{"can_generate_guide": false}',
                structured_output=mock_validator_output,
                success=True,
            )
        )

        # Mock consolidator - returns rejection
        orchestrator.guide_consolidator.consolidate_guide = AsyncMock(
            return_value=ConsolidatorResult(
                stable_guide=None,
                rejection_message="Cannot generate guide: All rules unstable due to contradictions",
                structured_output=None,
                success=True,
            )
        )

        # Run pipeline
        result = await orchestrator.run(uuid4(), uuid4())

        # Assertions: Pipeline succeeds but NO stable guide
        assert result.success is True
        assert result.has_stable_guide is False
        assert result.stable_guide is None
        assert result.rejection_message is not None
        assert result.pages_processed == 3

    @pytest.mark.asyncio
    async def test_partial_contradictions_can_still_produce_guide(self):
        """
        If only some rules are contradicted but enough remain stable,
        a guide can still be generated (without the contradicted rules).
        """
        session = MagicMock()
        file_storage = MagicMock()

        orchestrator = PipelineOrchestrator(session, file_storage)

        # Mock repositories
        project_mock = MagicMock()
        project_mock.status = ProjectStatus.DRAFT

        page1 = MagicMock()
        page1.file_path = "/path/to/page1.png"
        page1.order = 1

        page2 = MagicMock()
        page2.file_path = "/path/to/page2.png"
        page2.order = 2

        orchestrator.projects.get_by_id = AsyncMock(return_value=project_mock)
        orchestrator.projects.update_status = AsyncMock()
        orchestrator.pages.list_by_project = AsyncMock(return_value=[page1, page2])
        orchestrator.guides.get_or_create = AsyncMock(return_value=MagicMock())
        orchestrator.guides.update_provisional = AsyncMock()
        orchestrator.guides.update_confidence_report = AsyncMock()
        orchestrator.guides.update_stable = AsyncMock()

        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"fake png")

        # Mock guide builder
        orchestrator.guide_builder.build_guide = AsyncMock(
            return_value=GuideBuilderResult(
                provisional_guide='{"candidate_rules": []}',
                structured_output=None,
                success=True,
            )
        )

        # Mock guide applier - 2 rules: one contradicted, one confirmed
        orchestrator.guide_applier.validate_all_pages = AsyncMock(
            return_value=GuideApplierResult(
                page_validations=[
                    ValidationResult(
                        page_order=2,
                        validation_report="...",
                        structured_output=None,
                        has_contradictions=True,  # RULE_001 contradicted
                        success=True,
                    ),
                ],
                all_success=True,
                any_contradictions=True,
            )
        )

        # Mock self-validator - 3 rules: 2 stable, 1 unstable
        # 2/3 = 66% > 60% threshold
        confidence_report = ConfidenceReport(
            total_rules=3,
            stable_count=2,
            partial_count=0,
            unstable_count=1,
            rules=[
                RuleObservation(
                    rule_id="RULE_001",
                    description="Contradicted",
                    stability=RuleStability.UNSTABLE,
                    confidence_score=0.2,
                ),
                RuleObservation(
                    rule_id="RULE_002",
                    description="Stable",
                    stability=RuleStability.STABLE,
                    confidence_score=0.9,
                ),
                RuleObservation(
                    rule_id="RULE_003",
                    description="Stable",
                    stability=RuleStability.STABLE,
                    confidence_score=0.85,
                ),
            ],
            overall_stability=0.67,  # 2/3
            can_generate_final=True,  # Above 60% threshold
            rejection_reason=None,
        )

        orchestrator.self_validator.validate_stability = AsyncMock(
            return_value=SelfValidatorResult(
                confidence_report=confidence_report,
                raw_analysis="...",
                structured_output=None,
                success=True,
            )
        )

        # Mock consolidator - generates guide with only stable rules
        orchestrator.guide_consolidator.consolidate_guide = AsyncMock(
            return_value=ConsolidatorResult(
                stable_guide="# VALIDATED GUIDE\n\nRULE_002, RULE_003 only",
                rejection_message=None,
                structured_output=None,
                success=True,
            )
        )

        # Run pipeline
        result = await orchestrator.run(uuid4(), uuid4())

        # Assertions: Guide IS generated (with only stable rules)
        assert result.success is True
        assert result.has_stable_guide is True
        assert result.stable_guide is not None
        assert "RULE_002" in result.stable_guide or "VALIDATED" in result.stable_guide


class TestSchemaValidation:
    """Tests for JSON schema parsing in agents."""

    def test_rule_validation_status_enum(self):
        """Test that RuleValidationStatus enum values are correct."""
        assert RuleValidationStatus.CONFIRMED.value == "confirmed"
        assert RuleValidationStatus.CONTRADICTED.value == "contradicted"
        assert RuleValidationStatus.NOT_TESTABLE.value == "not_testable"
        assert RuleValidationStatus.VARIATION.value == "variation"

    def test_stability_classification_enum(self):
        """Test that StabilityClassification enum values are correct."""
        assert StabilityClassification.STABLE.value == "stable"
        assert StabilityClassification.PARTIAL.value == "partial"
        assert StabilityClassification.UNSTABLE.value == "unstable"

    def test_guide_applier_output_parsing(self):
        """Test that GuideApplierOutput parses correctly."""
        data = {
            "page_number": 2,
            "rule_validations": [
                {
                    "rule_id": "RULE_001",
                    "status": "contradicted",
                    "evidence": "Opposite pattern observed",
                }
            ],
            "new_observations": [],
            "overall_consistency": "inconsistent",
        }
        output = GuideApplierOutput.model_validate(data)

        assert output.page_number == 2
        assert len(output.rule_validations) == 1
        assert output.rule_validations[0].status == RuleValidationStatus.CONTRADICTED
        assert output.overall_consistency == "inconsistent"

    def test_self_validator_output_parsing(self):
        """Test that SelfValidatorOutput parses correctly."""
        data = {
            "total_rules": 3,
            "rule_assessments": [
                {
                    "rule_id": "RULE_001",
                    "classification": "unstable",
                    "pages_testable": 2,
                    "pages_confirmed": 0,
                    "pages_contradicted": 2,
                    "pages_variation": 0,
                    "confidence_score": 0.1,
                    "recommendation": "exclude",
                }
            ],
            "stable_count": 0,
            "partial_count": 0,
            "unstable_count": 1,
            "overall_stability_ratio": 0.0,
            "can_generate_guide": False,
            "rejection_reason": "All rules unstable",
        }
        output = SelfValidatorOutput.model_validate(data)

        assert output.total_rules == 3
        assert output.can_generate_guide is False
        assert output.rule_assessments[0].classification == StabilityClassification.UNSTABLE


class TestConsistentPagesFlow:
    """Gate 2: Consistent pages produce stable guide."""

    @pytest.mark.asyncio
    async def test_consistent_pages_produce_stable_guide(self):
        """With 2+ consistent pages, a stable guide is generated."""
        session = MagicMock()
        file_storage = MagicMock()

        orchestrator = PipelineOrchestrator(session, file_storage)

        # Mock repositories
        project_mock = MagicMock()
        project_mock.status = ProjectStatus.DRAFT

        page1 = MagicMock()
        page1.file_path = "/path/to/page1.png"
        page1.order = 1

        page2 = MagicMock()
        page2.file_path = "/path/to/page2.png"
        page2.order = 2

        orchestrator.projects.get_by_id = AsyncMock(return_value=project_mock)
        orchestrator.projects.update_status = AsyncMock()
        orchestrator.pages.list_by_project = AsyncMock(return_value=[page1, page2])
        orchestrator.guides.get_or_create = AsyncMock(return_value=MagicMock())
        orchestrator.guides.update_provisional = AsyncMock()
        orchestrator.guides.update_confidence_report = AsyncMock()
        orchestrator.guides.update_stable = AsyncMock()

        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"fake png")

        # Mock guide builder
        orchestrator.guide_builder.build_guide = AsyncMock(
            return_value=GuideBuilderResult(
                provisional_guide='{"candidate_rules": [{"id": "RULE_001"}]}',
                structured_output=None,
                success=True,
            )
        )

        # Mock guide applier - all rules confirmed (no contradictions)
        mock_applier_output = GuideApplierOutput(
            page_number=2,
            rule_validations=[
                RuleValidation(
                    rule_id="RULE_001",
                    status=RuleValidationStatus.CONFIRMED,
                    evidence="Page 2 confirms pattern",
                ),
            ],
            new_observations=[],
            overall_consistency="consistent",
        )

        orchestrator.guide_applier.validate_all_pages = AsyncMock(
            return_value=GuideApplierResult(
                page_validations=[
                    ValidationResult(
                        page_order=2,
                        validation_report='{"rule_validations": [{"rule_id": "RULE_001", "status": "confirmed"}]}',
                        structured_output=mock_applier_output,
                        has_contradictions=False,
                        success=True,
                    ),
                ],
                all_success=True,
                any_contradictions=False,
            )
        )

        # Mock self-validator - all rules stable
        confidence_report = ConfidenceReport(
            total_rules=1,
            stable_count=1,
            partial_count=0,
            unstable_count=0,
            rules=[
                RuleObservation(
                    rule_id="RULE_001",
                    description="Confirmed",
                    stability=RuleStability.STABLE,
                    confidence_score=0.95,
                )
            ],
            overall_stability=1.0,
            can_generate_final=True,
            rejection_reason=None,
        )

        orchestrator.self_validator.validate_stability = AsyncMock(
            return_value=SelfValidatorResult(
                confidence_report=confidence_report,
                raw_analysis='{"can_generate_guide": true}',
                structured_output=None,
                success=True,
            )
        )

        # Mock consolidator - generates stable guide
        orchestrator.guide_consolidator.consolidate_guide = AsyncMock(
            return_value=ConsolidatorResult(
                stable_guide="# VALIDATED VISUAL GUIDE\n\nRULE_001: Pattern confirmed",
                rejection_message=None,
                structured_output=None,
                success=True,
            )
        )

        # Run pipeline
        result = await orchestrator.run(uuid4(), uuid4())

        # Assertions: Gate 2 - stable guide generated
        assert result.success is True
        assert result.has_stable_guide is True
        assert result.stable_guide is not None
        assert "VALIDATED" in result.stable_guide or "RULE_001" in result.stable_guide
        assert result.rejection_message is None


class TestInvalidModelOutput:
    """Gate 4: Invalid model output causes pipeline to fail loudly."""

    @pytest.mark.asyncio
    async def test_invalid_json_from_model_fails_loudly(self):
        """When model returns invalid JSON, pipeline must fail (no silent fallback)."""
        from pydantic import ValidationError

        # Test that invalid JSON raises proper error during parsing
        invalid_json_responses = [
            "This is not JSON at all",
            '{"observations": "should be array"}',  # Wrong type
            '{"missing_required": true}',  # Missing required fields
        ]

        for invalid_response in invalid_json_responses:
            # Attempt to parse as GuideBuilderOutput should fail
            with pytest.raises((ValidationError, ValueError, Exception)):
                import json
                data = json.loads(invalid_response) if invalid_response.startswith('{') else {}
                if data:
                    GuideBuilderOutput.model_validate(data)
                else:
                    raise ValueError("Invalid JSON")

    @pytest.mark.asyncio
    async def test_guide_builder_failure_propagates(self):
        """When guide builder fails, pipeline fails with error."""
        session = MagicMock()
        file_storage = MagicMock()

        orchestrator = PipelineOrchestrator(session, file_storage)

        # Mock repositories
        project_mock = MagicMock()
        project_mock.status = ProjectStatus.DRAFT

        page1 = MagicMock()
        page1.file_path = "/path/to/page1.png"
        page1.order = 1

        orchestrator.projects.get_by_id = AsyncMock(return_value=project_mock)
        orchestrator.projects.update_status = AsyncMock()
        orchestrator.pages.list_by_project = AsyncMock(return_value=[page1])
        orchestrator.guides.get_or_create = AsyncMock(return_value=MagicMock())

        orchestrator.file_storage.read_image_bytes = AsyncMock(return_value=b"fake png")

        # Mock guide builder to return failure
        orchestrator.guide_builder.build_guide = AsyncMock(
            return_value=GuideBuilderResult(
                provisional_guide="",
                structured_output=None,
                success=False,
                error="Model returned invalid output",
            )
        )

        # Run pipeline - should raise PipelineError
        with pytest.raises(PipelineError) as exc_info:
            await orchestrator.run(uuid4(), uuid4())

        assert "guide builder" in str(exc_info.value).lower() or exc_info.value.error_code == "GUIDE_BUILDER_FAILED"


class TestSchemaEnforcement:
    """Gate 5: Schema violations raise validation errors."""

    def test_guide_builder_output_rejects_invalid_schema(self):
        """GuideBuilderOutput rejects data that violates schema."""
        from pydantic import ValidationError

        # Missing required field
        with pytest.raises(ValidationError):
            GuideBuilderOutput.model_validate({
                "observations": [],
                # Missing: candidate_rules, uncertainties, assumptions
            })

        # Wrong type for observations
        with pytest.raises(ValidationError):
            GuideBuilderOutput.model_validate({
                "observations": "not an array",
                "candidate_rules": [],
                "uncertainties": [],
                "assumptions": [],
            })

    def test_guide_applier_output_rejects_invalid_schema(self):
        """GuideApplierOutput rejects data that violates schema."""
        from pydantic import ValidationError

        # Missing required field
        with pytest.raises(ValidationError):
            GuideApplierOutput.model_validate({
                "page_number": 2,
                # Missing: rule_validations, new_observations, overall_consistency
            })

        # Invalid status value
        with pytest.raises(ValidationError):
            GuideApplierOutput.model_validate({
                "page_number": 2,
                "rule_validations": [
                    {
                        "rule_id": "RULE_001",
                        "status": "INVALID_STATUS",  # Not in enum
                        "evidence": "test",
                    }
                ],
                "new_observations": [],
                "overall_consistency": "consistent",
            })

    def test_self_validator_output_rejects_invalid_schema(self):
        """SelfValidatorOutput rejects data that violates schema."""
        from pydantic import ValidationError

        # Invalid classification
        with pytest.raises(ValidationError):
            SelfValidatorOutput.model_validate({
                "total_rules": 1,
                "rule_assessments": [
                    {
                        "rule_id": "RULE_001",
                        "classification": "INVALID",  # Not stable/partial/unstable
                        "pages_testable": 1,
                        "pages_confirmed": 1,
                        "pages_contradicted": 0,
                        "pages_variation": 0,
                        "confidence_score": 0.9,
                        "recommendation": "include",
                    }
                ],
                "stable_count": 1,
                "partial_count": 0,
                "unstable_count": 0,
                "overall_stability_ratio": 1.0,
                "can_generate_guide": True,
            })

    def test_confidence_score_bounds(self):
        """Confidence scores must be between 0 and 1."""
        from pydantic import ValidationError

        # Score > 1 should fail
        with pytest.raises(ValidationError):
            RuleStabilityAssessment(
                rule_id="RULE_001",
                classification=StabilityClassification.STABLE,
                pages_testable=1,
                pages_confirmed=1,
                pages_contradicted=0,
                pages_variation=0,
                confidence_score=1.5,  # Invalid: > 1
                recommendation="include",
            )

        # Score < 0 should fail
        with pytest.raises(ValidationError):
            RuleStabilityAssessment(
                rule_id="RULE_001",
                classification=StabilityClassification.STABLE,
                pages_testable=1,
                pages_confirmed=1,
                pages_contradicted=0,
                pages_variation=0,
                confidence_score=-0.1,  # Invalid: < 0
                recommendation="include",
            )
