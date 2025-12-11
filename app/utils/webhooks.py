"""Webhook notification system for duplicate detection events."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from flask import current_app

from app import db
from app.models.bug import Bug

logger = logging.getLogger(__name__)


class WebhookEvent:
    """Webhook event types."""

    DUPLICATE_DETECTED = "duplicate.detected"
    DUPLICATE_BLOCKED = "duplicate.blocked"
    LOW_QUALITY = "bug.low_quality"
    QUALITY_APPROVED = "bug.quality_approved"
    JIRA_SYNCED = "bug.jira_synced"
    TP_SYNCED = "bug.tp_synced"
    RECURRING_PATTERN = "bug.recurring_pattern"


class WebhookNotifier:
    """Send webhook notifications for bug deduplication events."""

    def __init__(self, webhook_urls: Optional[List[str]] = None):
        """
        Initialize webhook notifier.

        Args:
            webhook_urls: List of webhook URLs to send notifications to
        """
        self.webhook_urls = webhook_urls or []

    def notify(
        self,
        event_type: str,
        bug: Bug,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send webhook notification for an event.

        Args:
            event_type: Type of event (from WebhookEvent)
            bug: Bug object
            additional_data: Additional event data
        """
        if not self.webhook_urls:
            logger.debug("No webhook URLs configured, skipping notification")
            return

        payload = self._build_payload(event_type, bug, additional_data)

        for url in self.webhook_urls:
            try:
                self._send_webhook(url, payload)
            except Exception as e:
                logger.error(f"Failed to send webhook to {url}: {e}")

    def _build_payload(
        self,
        event_type: str,
        bug: Bug,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build webhook payload."""
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "bug": {
                "id": str(bug.id),
                "title": bug.title,
                "product": bug.product,
                "component": bug.component,
                "severity": bug.severity,
                "status": bug.status,
                "quality_score": bug.quality_score,
                "is_duplicate": bug.is_duplicate,
                "jira_key": bug.jira_key,
                "tp_defect_id": bug.tp_defect_id,
                "created_at": bug.created_at.isoformat(),
            },
        }

        # Add duplicate information if applicable
        if bug.is_duplicate and bug.duplicate_of_id:
            duplicate_of = Bug.query.get(bug.duplicate_of_id)
            if duplicate_of:
                payload["duplicate_of"] = {
                    "id": str(duplicate_of.id),
                    "title": duplicate_of.title,
                    "jira_key": duplicate_of.jira_key,
                }
                payload["similarity_score"] = bug.similarity_score

        # Merge additional data
        if additional_data:
            payload.update(additional_data)

        return payload

    def _send_webhook(self, url: str, payload: Dict[str, Any]) -> None:
        """
        Send webhook HTTP POST request.

        Args:
            url: Webhook URL
            payload: JSON payload
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BugDeduplicationSystem/1.0",
        }

        # Add signature if secret is configured
        if secret := current_app.config.get("WEBHOOK_SECRET"):
            import hmac
            import hashlib
            import json

            message = json.dumps(payload, sort_keys=True).encode()
            signature = hmac.new(
                secret.encode(), message, hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()

        logger.info(
            f"Webhook sent successfully to {url}, "
            f"event={payload['event']}, bug_id={payload['bug']['id']}"
        )

    def notify_duplicate_detected(
        self,
        bug: Bug,
        duplicate_of: Bug,
        similarity_score: float,
        action_taken: str,
    ) -> None:
        """Notify when duplicate is detected."""
        event_type = (
            WebhookEvent.DUPLICATE_BLOCKED
            if action_taken == "blocked"
            else WebhookEvent.DUPLICATE_DETECTED
        )

        self.notify(
            event_type,
            bug,
            {
                "duplicate_of": {
                    "id": str(duplicate_of.id),
                    "title": duplicate_of.title,
                    "jira_key": duplicate_of.jira_key,
                },
                "similarity_score": similarity_score,
                "action_taken": action_taken,
            },
        )

    def notify_low_quality(self, bug: Bug, quality_issues: List[str]) -> None:
        """Notify when low quality bug is submitted."""
        self.notify(
            WebhookEvent.LOW_QUALITY,
            bug,
            {"quality_issues": quality_issues},
        )

    def notify_jira_sync(self, bug: Bug, jira_key: str) -> None:
        """Notify when bug is synced to Jira."""
        self.notify(
            WebhookEvent.JIRA_SYNCED,
            bug,
            {"jira_key": jira_key},
        )

    def notify_tp_sync(self, bug: Bug, tp_defect_id: str) -> None:
        """Notify when bug is synced to Test Platform."""
        self.notify(
            WebhookEvent.TP_SYNCED,
            bug,
            {"tp_defect_id": tp_defect_id},
        )

    def notify_recurring_pattern(
        self,
        bug: Bug,
        duplicate_count: int,
    ) -> None:
        """Notify when recurring bug pattern is detected."""
        self.notify(
            WebhookEvent.RECURRING_PATTERN,
            bug,
            {
                "duplicate_count": duplicate_count,
                "message": f"Bug has {duplicate_count} duplicates - possible systemic issue",
            },
        )


def get_webhook_notifier() -> WebhookNotifier:
    """Get webhook notifier instance from app config."""
    webhook_urls = current_app.config.get("WEBHOOK_URLS", [])

    if isinstance(webhook_urls, str):
        webhook_urls = [url.strip() for url in webhook_urls.split(",") if url.strip()]

    return WebhookNotifier(webhook_urls)
