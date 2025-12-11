"""
Test Platform (TP) integration for syncing test results
"""

import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class TPIntegration:
    """Integration with Test Platform"""

    def __init__(self, api_url: str, api_key: str, project_id: str):
        """
        Initialize TP integration

        Args:
            api_url: Test Platform API URL
            api_key: API authentication key
            project_id: Project identifier
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.project_id = project_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def create_defect(self, bug_data: Dict) -> Optional[str]:
        """
        Create a defect in TP

        Args:
            bug_data: Bug information

        Returns:
            TP defect ID or None if failed
        """
        try:
            payload = {
                "project_id": self.project_id,
                "title": bug_data.get("title"),
                "description": bug_data.get("description"),
                "severity": bug_data.get("severity", "Medium"),
                "priority": bug_data.get("priority", "Medium"),
                "reporter": bug_data.get("reporter"),
                "environment": {
                    "device": bug_data.get("device"),
                    "os_version": bug_data.get("os_version"),
                    "build_version": bug_data.get("build_version"),
                    "region": bug_data.get("region"),
                },
                "repro_steps": bug_data.get("repro_steps"),
                "logs": bug_data.get("logs"),
            }

            response = requests.post(
                f"{self.api_url}/defects",
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            defect_id = data.get("id") or data.get("defect_id")

            logger.info(f"Created TP defect: {defect_id}")
            return str(defect_id)

        except Exception as e:
            logger.error(f"Failed to create TP defect: {e}")
            return None

    def update_defect(self, defect_id: str, updates: Dict) -> bool:
        """
        Update a TP defect

        Args:
            defect_id: TP defect ID
            updates: Fields to update

        Returns:
            True if successful
        """
        try:
            response = requests.patch(
                f"{self.api_url}/defects/{defect_id}",
                json=updates,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Updated TP defect: {defect_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update TP defect {defect_id}: {e}")
            return False

    def add_tag(self, defect_id: str, tag: str) -> bool:
        """
        Add a tag to a TP defect

        Args:
            defect_id: TP defect ID
            tag: Tag to add (Duplicate, Recurring, LowQuality)

        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.api_url}/defects/{defect_id}/tags",
                json={"tag": tag},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Added tag '{tag}' to TP defect: {defect_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add tag to TP defect {defect_id}: {e}")
            return False

    def link_defects(self, parent_id: str, duplicate_id: str) -> bool:
        """
        Link two defects as duplicate relationship

        Args:
            parent_id: Original defect ID
            duplicate_id: Duplicate defect ID

        Returns:
            True if successful
        """
        try:
            payload = {
                "link_type": "duplicate",
                "parent_defect_id": parent_id,
                "child_defect_id": duplicate_id,
            }

            response = requests.post(
                f"{self.api_url}/defects/links",
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Linked TP defects: {duplicate_id} -> {parent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to link TP defects: {e}")
            return False

    def add_comment(self, defect_id: str, comment: str) -> bool:
        """
        Add a comment to a TP defect

        Args:
            defect_id: TP defect ID
            comment: Comment text

        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.api_url}/defects/{defect_id}/comments",
                json={"comment": comment},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Added comment to TP defect: {defect_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add comment to TP defect {defect_id}: {e}")
            return False

    def update_duplicate_status(
        self, parent_id: str, duplicate_id: str, match_score: float
    ) -> bool:
        """
        Update TP when a duplicate is detected

        Args:
            parent_id: Original defect ID
            duplicate_id: Duplicate defect ID
            match_score: AI match score

        Returns:
            True if successful
        """
        # Add Duplicate tag
        self.add_tag(duplicate_id, "Duplicate")

        # Link the defects
        self.link_defects(parent_id, duplicate_id)

        # Add comment with match details
        comment = (
            f"This defect has been automatically identified as a duplicate of #{parent_id}\\n"
            f"AI Match Score: {match_score:.2%}\\n"
            f"Please review and confirm the classification."
        )
        self.add_comment(duplicate_id, comment)

        # Add reference comment to parent
        parent_comment = f"Duplicate defect detected: #{duplicate_id} (Match Score: {match_score:.2%})"
        self.add_comment(parent_id, parent_comment)

        return True

    def mark_as_recurring(self, defect_id: str, duplicate_count: int) -> bool:
        """
        Mark a TP defect as recurring

        Args:
            defect_id: TP defect ID
            duplicate_count: Number of duplicates

        Returns:
            True if successful
        """
        # Add Recurring tag
        self.add_tag(defect_id, "Recurring")

        # Update priority/severity if needed
        self.update_defect(
            defect_id,
            {
                "priority": "High",
                "notes": f"Marked as RECURRING - {duplicate_count} duplicate reports detected",
            },
        )

        # Add comment
        comment = (
            f"This defect has been marked as RECURRING\\n"
            f"Number of duplicate reports: {duplicate_count}\\n"
            f"This indicates a pattern that requires immediate attention."
        )
        self.add_comment(defect_id, comment)

        return True
