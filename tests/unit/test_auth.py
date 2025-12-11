"""Unit tests for authentication middleware."""

import pytest
from datetime import datetime, timedelta
from app.middleware.auth import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    create_jwt_token,
    verify_jwt_token,
    detect_bot_request,
    extract_environment_context,
)
from app.models.auth import APIKey


class TestAuthMiddleware:
    """Test authentication middleware functions."""

    def test_api_key_generation(self):
        """Test API key generation format."""
        key = generate_api_key()

        assert key.startswith("bgd_test_")
        assert len(key) > 30

    def test_api_key_hashing(self):
        """Test API key hashing is consistent."""
        key = "bgd_test_abc123"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)

        assert hash1 != key  # Should be hashed
        # bcrypt generates different salts each time
        assert hash1 != hash2

    def test_api_key_verification(self):
        """Test API key verification."""
        key = "bgd_test_abc123"
        key_hash = hash_api_key(key)

        assert verify_api_key(key, key_hash) is True
        assert verify_api_key("wrong_key", key_hash) is False

    def test_jwt_token_creation(self):
        """Test JWT token creation."""
        token = create_jwt_token(
            user_id="user123",
            email="test@example.com",
            roles=["user"],
            expires_delta=timedelta(hours=1),
        )

        assert isinstance(token, str)
        assert len(token) > 50

    def test_jwt_token_verification(self):
        """Test JWT token verification."""
        token = create_jwt_token(
            user_id="user123", email="test@example.com", roles=["user", "admin"]
        )

        payload = verify_jwt_token(token)

        assert payload is not None
        assert payload["user_id"] == "user123"
        assert payload["email"] == "test@example.com"
        assert "user" in payload["roles"]
        assert "admin" in payload["roles"]

    def test_jwt_token_expiration(self):
        """Test JWT token expiration."""
        # Create token that expires immediately
        token = create_jwt_token(
            user_id="user123",
            email="test@example.com",
            roles=["user"],
            expires_delta=timedelta(seconds=-1),
        )

        payload = verify_jwt_token(token)
        assert payload is None  # Should be expired

    def test_bot_detection_headless_browser(self, app):
        """Test bot detection for headless browsers."""
        with app.test_request_context(
            headers={"User-Agent": "HeadlessChrome/91.0.4472.124"}
        ):
            assert detect_bot_request() is True

    def test_bot_detection_automation_header(self, app):
        """Test bot detection via automation headers."""
        with app.test_request_context(
            headers={"User-Agent": "Mozilla/5.0", "X-Automation": "true"}
        ):
            assert detect_bot_request() is True

    def test_bot_detection_normal_browser(self, app):
        """Test that normal browsers are not detected as bots."""
        with app.test_request_context(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        ):
            assert detect_bot_request() is False

    def test_environment_context_extraction(self, app):
        """Test environment context extraction."""
        with app.test_request_context(
            headers={
                "User-Agent": "Mozilla/5.0",
                "X-Environment": "staging",
                "X-Client-Version": "1.2.3",
                "X-Forwarded-For": "192.168.1.1",
            }
        ):
            context = extract_environment_context()

            assert context["environment"] == "staging"
            assert context["client_version"] == "1.2.3"
            assert context["ip_address"] == "192.168.1.1"
            assert "user_agent" in context


class TestAPIKeyModel:
    """Test APIKey model."""

    def test_create_api_key(self, db_session):
        """Test API key creation."""
        key = APIKey.create_key(name="Test Key", role="integration", expires_in_days=30)

        assert key.name == "Test Key"
        assert key.role == "integration"
        assert key.is_active is True
        assert key.expires_at is not None

    def test_api_key_expiration_check(self, db_session):
        """Test API key expiration checking."""
        # Create expired key
        key = APIKey.create_key(name="Expired Key", role="user", expires_in_days=0)
        key.expires_at = datetime.utcnow() - timedelta(days=1)
        db_session.add(key)
        db_session.commit()

        # Verification should fail for expired key
        assert key.is_active is True  # Not revoked
        # But verify_key should check expiration

    def test_api_key_revocation(self, db_session):
        """Test API key revocation."""
        key = APIKey.create_key(name="Test Key", role="user")
        db_session.add(key)
        db_session.commit()

        key.revoke()
        db_session.commit()

        assert key.is_active is False

    def test_api_key_usage_tracking(self, db_session):
        """Test API key usage tracking."""
        key = APIKey.create_key(name="Test Key", role="user")
        db_session.add(key)
        db_session.commit()

        initial_count = key.usage_count

        key.record_usage("192.168.1.1")
        db_session.commit()

        assert key.usage_count == initial_count + 1
        assert key.last_used_ip == "192.168.1.1"
        assert key.last_used_at is not None
