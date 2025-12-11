"""Unit tests for quality checker."""

import pytest
from app.services.quality_checker import QualityChecker


class TestQualityChecker:
    """Test quality checking logic."""

    @pytest.fixture
    def checker(self):
        return QualityChecker(
            min_description_length=20, require_repro_steps=True, require_logs=False
        )

    def test_high_quality_bug(self, checker):
        """Test validation of high quality bug."""
        bug_data = {
            "title": "Login button not responding on mobile Safari",
            "description": "When clicking the login button on iOS Safari 16.1, "
            "the application does not respond. Expected behavior is successful login.",
            "steps_to_reproduce": [
                "Open app on iOS device",
                "Navigate to login page",
                "Enter valid credentials",
                "Click login button",
            ],
            "expected_result": "User should be logged in",
            "actual_result": "No response from button",
        }

        is_valid, score, issues = checker.validate_bug(bug_data)

        assert is_valid is True
        assert score >= 0.8
        assert len(issues) == 0

    def test_short_description_fails(self, checker):
        """Test that short description fails validation."""
        bug_data = {
            "title": "Bug in login",
            "description": "Login broke",
            "steps_to_reproduce": ["Click button"],
        }

        is_valid, score, issues = checker.validate_bug(bug_data)

        assert is_valid is False
        assert score < 0.6
        assert any("description" in issue.lower() for issue in issues)

    def test_missing_repro_steps_fails(self, checker):
        """Test that missing reproduction steps fails when required."""
        bug_data = {
            "title": "Login button not responding",
            "description": "The login button does not work when clicked on mobile devices.",
        }

        is_valid, score, issues = checker.validate_bug(bug_data)

        assert is_valid is False
        assert any("reproduction steps" in issue.lower() for issue in issues)

    def test_vague_title_reduces_score(self, checker):
        """Test that vague title reduces quality score."""
        bug_data = {
            "title": "Bug",
            "description": "The login functionality is not working correctly on mobile devices.",
            "steps_to_reproduce": ["Open app", "Try to login"],
        }

        is_valid, score, issues = checker.validate_bug(bug_data)

        assert score < 0.7
        assert any("title" in issue.lower() for issue in issues)

    def test_detailed_bug_gets_high_score(self, checker):
        """Test that detailed bug gets high quality score."""
        bug_data = {
            "title": "Login button unresponsive on iOS Safari 16.1 in production",
            "description": "When users attempt to login using the mobile app on iOS Safari 16.1, "
            "the login button does not respond to touch events. This issue occurs consistently "
            "in production environment. Browser console shows no errors.",
            "steps_to_reproduce": [
                "Open mobile app on iOS device with Safari 16.1",
                "Navigate to login page",
                "Enter valid credentials (email: test@example.com, password: Test123)",
                "Tap the login button",
                "Observe: Button does not respond, no visual feedback",
            ],
            "expected_result": "User should be authenticated and redirected to dashboard",
            "actual_result": "Login button does not respond to touch events, user remains on login page",
            "attachments": ["screenshot.png", "console_log.txt"],
        }

        is_valid, score, issues = checker.validate_bug(bug_data)

        assert is_valid is True
        assert score >= 0.9
        assert len(issues) == 0
