"""
Jira integration for syncing bugs and duplicates
"""

import logging
from typing import Dict, Optional

from jira import JIRA

logger = logging.getLogger(__name__)


class JiraIntegration:
    """Integration with Jira for bug tracking"""

    def __init__(self, url: str, username: str, api_token: str, project_key: str):
        """
        Initialize Jira integration

        Args:
            url: Jira instance URL
            username: Jira username/email
            api_token: Jira API token
            project_key: Jira project key
        """
        self.project_key = project_key

        try:
            self.client = JIRA(server=url, basic_auth=(username, api_token))
            logger.info(f"Connected to Jira: {url}")
        except Exception as e:
            logger.error(f"Failed to connect to Jira: {e}")
            self.client = None

    def create_issue(self, bug_data: Dict) -> Optional[str]:
        """
        Create a new Jira issue

        Args:
            bug_data: Bug information

        Returns:
            Jira issue key or None if failed
        """
        if not self.client:
            logger.warning("Jira client not initialized")
            return None

        try:
            issue_dict = {
                "project": {"key": self.project_key},
                "summary": bug_data.get("title"),
                "description": self._format_description(bug_data),
                "issuetype": {"name": "Bug"},
            }

            # Add optional fields
            if severity := bug_data.get("severity"):
                issue_dict["priority"] = {"name": severity}

            issue = self.client.create_issue(fields=issue_dict)
            logger.info(f"Created Jira issue: {issue.key}")

            return issue.key

        except Exception as e:
            logger.error(f"Failed to create Jira issue: {e}")
            return None

    def update_issue(self, jira_key: str, updates: Dict) -> bool:
        """
        Update a Jira issue

        Args:
            jira_key: Jira issue key
            updates: Fields to update

        Returns:
            True if successful
        """
        if not self.client:
            return False

        try:
            issue = self.client.issue(jira_key)
            issue.update(fields=updates)
            logger.info(f"Updated Jira issue: {jira_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to update Jira issue {jira_key}: {e}")
            return False

    def add_label(self, jira_key: str, label: str) -> bool:
        """
        Add a label to a Jira issue

        Args:
            jira_key: Jira issue key
            label: Label to add (Duplicate, Recurring, LowQuality)

        Returns:
            True if successful
        """
        if not self.client:
            return False

        try:
            issue = self.client.issue(jira_key)
            current_labels = issue.fields.labels

            if label not in current_labels:
                current_labels.append(label)
                issue.update(fields={"labels": current_labels})
                logger.info(f"Added label '{label}' to Jira issue: {jira_key}")

            return True

        except Exception as e:
            logger.error(f"Failed to add label to Jira issue {jira_key}: {e}")
            return False

    def link_issues(self, parent_key: str, duplicate_key: str) -> bool:
        """
        Link two issues as duplicate relationship

        Args:
            parent_key: Original bug Jira key
            duplicate_key: Duplicate bug Jira key

        Returns:
            True if successful
        """
        if not self.client:
            return False

        try:
            self.client.create_issue_link(
                type="Duplicate",
                inwardIssue=duplicate_key,
                outwardIssue=parent_key,
                comment={"body": "Automatically detected as duplicate by AI system"},
            )
            logger.info(f"Linked Jira issues: {duplicate_key} -> {parent_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to link Jira issues: {e}")
            return False

    def add_comment(self, jira_key: str, comment: str) -> bool:
        """
        Add a comment to a Jira issue

        Args:
            jira_key: Jira issue key
            comment: Comment text

        Returns:
            True if successful
        """
        if not self.client:
            return False

        try:
            issue = self.client.issue(jira_key)
            self.client.add_comment(issue, comment)
            logger.info(f"Added comment to Jira issue: {jira_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to add comment to Jira issue {jira_key}: {e}")
            return False

    def update_duplicate_status(
        self, parent_key: str, duplicate_key: str, match_score: float
    ) -> bool:
        """
        Update Jira when a duplicate is detected

        Args:
            parent_key: Original bug Jira key
            duplicate_key: Duplicate bug Jira key
            match_score: AI match score

        Returns:
            True if successful
        """
        # Add Duplicate label to duplicate issue
        self.add_label(duplicate_key, "Duplicate")

        # Link the issues
        self.link_issues(parent_key, duplicate_key)

        # Add comment with match details
        comment = (
            f"This issue has been automatically identified as a duplicate of {parent_key}\\n"
            f"AI Match Score: {match_score:.2%}\\n"
            f"Please review and confirm the classification."
        )
        self.add_comment(duplicate_key, comment)

        # Add reference comment to parent
        parent_comment = (
            f"Duplicate issue detected: {duplicate_key}\\n"
            f"AI Match Score: {match_score:.2%}"
        )
        self.add_comment(parent_key, parent_comment)

        return True

    def mark_as_recurring(self, jira_key: str, duplicate_count: int) -> bool:
        """
        Mark a Jira issue as recurring

        Args:
            jira_key: Jira issue key
            duplicate_count: Number of duplicates

        Returns:
            True if successful
        """
        # Add Recurring label
        self.add_label(jira_key, "Recurring")

        # Add comment
        comment = (
            f"This issue has been marked as RECURRING\\n"
            f"Number of duplicate reports: {duplicate_count}\\n"
            f"This indicates a pattern that requires attention."
        )
        self.add_comment(jira_key, comment)

        return True

    def _format_description(self, bug_data: Dict) -> str:
        """Format bug data into Jira description"""
        parts = [bug_data.get("description", "")]

        if repro_steps := bug_data.get("repro_steps"):
            parts.append(f"\\n\\n*Reproduction Steps:*\\n{repro_steps}")

        if device := bug_data.get("device"):
            parts.append(f"\\n*Device:* {device}")

        if os_version := bug_data.get("os_version"):
            parts.append(f"\\n*OS Version:* {os_version}")

        if build_version := bug_data.get("build_version"):
            parts.append(f"\\n*Build Version:* {build_version}")

        if region := bug_data.get("region"):
            parts.append(f"\\n*Region:* {region}")

        if logs := bug_data.get("logs"):
            parts.append(f"\\n\\n*Logs:*\\n{{code}}\\n{logs}\\n{{code}}")

        return "".join(parts)
