"""Tests for data models and entities."""

import pytest
from uuid import uuid4

from src.models.entities import (
    Project,
    ProjectStatus,
    Page,
    VisualGuide,
    RuleStability,
    RuleObservation,
    ConfidenceReport,
)


class TestProject:
    """Tests for Project entity."""

    def test_create_project(self):
        """Test project creation with defaults."""
        owner_id = uuid4()
        project = Project(owner_id=owner_id)

        assert project.id is not None
        assert project.status == ProjectStatus.DRAFT
        assert project.owner_id == owner_id
        assert project.created_at is not None

    def test_project_status_values(self):
        """Test all project status values exist."""
        assert ProjectStatus.DRAFT == "draft"
        assert ProjectStatus.PROCESSING == "processing"
        assert ProjectStatus.VALIDATED == "validated"
        assert ProjectStatus.FAILED == "failed"


class TestPage:
    """Tests for Page entity."""

    def test_create_page(self):
        """Test page creation."""
        project_id = uuid4()
        page = Page(
            project_id=project_id,
            order=1,
            file_path="test/path.png",
        )

        assert page.id is not None
        assert page.project_id == project_id
        assert page.order == 1
        assert page.file_path == "test/path.png"

    def test_page_order_validation(self):
        """Test page order must be >= 1."""
        with pytest.raises(ValueError):
            Page(
                project_id=uuid4(),
                order=0,
                file_path="test.png",
            )


class TestConfidenceReport:
    """Tests for ConfidenceReport entity."""

    def test_create_empty_report(self):
        """Test creating empty confidence report."""
        report = ConfidenceReport()

        assert report.total_rules == 0
        assert report.stable_count == 0
        assert report.can_generate_final is False

    def test_report_with_rules(self):
        """Test confidence report with rules."""
        rules = [
            RuleObservation(
                rule_id="RULE_1",
                description="Test rule 1",
                stability=RuleStability.STABLE,
                confidence_score=0.9,
            ),
            RuleObservation(
                rule_id="RULE_2",
                description="Test rule 2",
                stability=RuleStability.UNSTABLE,
                confidence_score=0.2,
            ),
        ]

        report = ConfidenceReport(
            total_rules=2,
            stable_count=1,
            unstable_count=1,
            rules=rules,
            overall_stability=0.5,
            can_generate_final=False,
            rejection_reason="Insufficient stable rules",
        )

        assert len(report.rules) == 2
        assert report.can_generate_final is False

    def test_rule_stability_values(self):
        """Test all rule stability values."""
        assert RuleStability.STABLE == "stable"
        assert RuleStability.PARTIAL == "partial"
        assert RuleStability.UNSTABLE == "unstable"


class TestVisualGuide:
    """Tests for VisualGuide entity."""

    def test_create_guide(self):
        """Test visual guide creation."""
        project_id = uuid4()
        guide = VisualGuide(project_id=project_id)

        assert guide.id is not None
        assert guide.project_id == project_id
        assert guide.provisional is None
        assert guide.stable is None
        assert guide.confidence_report is None

    def test_guide_with_content(self):
        """Test guide with all content."""
        project_id = uuid4()
        report = ConfidenceReport(
            total_rules=5,
            stable_count=4,
            overall_stability=0.8,
            can_generate_final=True,
        )

        guide = VisualGuide(
            project_id=project_id,
            provisional="Provisional guide content",
            stable="Stable guide content",
            confidence_report=report,
        )

        assert guide.provisional == "Provisional guide content"
        assert guide.stable == "Stable guide content"
        assert guide.confidence_report.can_generate_final is True
