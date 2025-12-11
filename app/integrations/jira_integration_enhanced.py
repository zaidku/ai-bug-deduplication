"""Enhanced Jira integration with circuit breaker and retry logic."""

import logging
from typing import Dict, Optional
from jira import JIRA
from jira.exceptions import JIRAError

from app.utils.circuit_breaker import (
    circuit_breaker,
    retry_with_backoff,
    CircuitBreakerOpenError,
)
from app.utils.metrics import track_jira_sync

logger = logging.getLogger(__name__)


class JiraIntegration:
    """Jira integration with resilience patterns."""

    def __init__(self, url: str, username: str, api_token: str, project_key: str):
        self.url = url
        self.username = username
        self.api_token = api_token
        self.project_key = project_key
        self._client = None

    @property
    def client(self):
        """Lazy initialize Jira client."""
        if self._client is None:
            self._client = JIRA(
                server=self.url, basic_auth=(self.username, self.api_token)
            )
        return self._client

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    @circuit_breaker(
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=JIRAError,
        name="jira_create_issue",
    )
    def create_issue(self, bug_data: Dict) -> Optional[str]:
        """
        Create Jira issue with circuit breaker and retry.

        Args:
            bug_data: Bug information

        Returns:
            Jira issue key (e.g., 'BUGS-1234')
        """
        try:
            issue_dict = {
                "project": {"key": self.project_key},
                "summary": bug_data["title"],
                "description": self._format_description(bug_data),
                "issuetype": {"name": "Bug"},
                "priority": {
                    "name": self._map_severity(bug_data.get("severity", "minor"))
                },
                "labels": bug_data.get("tags", []),
            }

            # Add custom fields if available
            if bug_data.get("environment"):
                issue_dict["environment"] = bug_data["environment"]

            if bug_data.get("version"):
                issue_dict["versions"] = [{"name": bug_data["version"]}]

            # Create issue
            issue = self.client.create_issue(fields=issue_dict)

            logger.info(f"Created Jira issue: {issue.key}")
            track_jira_sync(success=True)

            return issue.key

        except CircuitBreakerOpenError:
            logger.error("Jira circuit breaker is open, skipping issue creation")
            track_jira_sync(success=False)
            return None

        except JIRAError as e:
            logger.error(f"Failed to create Jira issue: {e}")
            track_jira_sync(success=False)
            raise

    @retry_with_backoff(max_retries=2)
    @circuit_breaker(
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=JIRAError,
        name="jira_link_issues",
    )
    def link_duplicate(self, issue_key: str, duplicate_of_key: str):
        """Link duplicate issues."""
        try:
            self.client.create_issue_link(
                type="Duplicate", inwardIssue=issue_key, outwardIssue=duplicate_of_key
            )
            logger.info(f"Linked {issue_key} as duplicate of {duplicate_of_key}")

        except CircuitBreakerOpenError:
            logger.warning("Jira circuit breaker open, skipping link creation")

        except JIRAError as e:
            logger.error(f"Failed to link issues: {e}")
            raise

    def _format_description(self, bug_data: Dict) -> str:
        """Format bug description for Jira."""
        parts = [bug_data["description"]]

        if steps := bug_data.get("steps_to_reproduce"):
            parts.append("\n\nh3. Steps to Reproduce:")
            for i, step in enumerate(steps, 1):
                parts.append(f"{i}. {step}")

        if expected := bug_data.get("expected_result"):
            parts.append(f"\n\nh3. Expected Result:\n{expected}")

        if actual := bug_data.get("actual_result"):
            parts.append(f"\n\nh3. Actual Result:\n{actual}")

        return "\n".join(parts)

    @staticmethod
    def _map_severity(severity: str) -> str:
        """Map bug severity to Jira priority."""
        mapping = {
            "critical": "Highest",
            "major": "High",
            "minor": "Medium",
            "trivial": "Low",
        }
        return mapping.get(severity.lower(), "Medium")
