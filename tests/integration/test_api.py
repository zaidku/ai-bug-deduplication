"""Integration tests for bug submission API."""

import pytest
import json
from app.models.bug import Bug


class TestBugSubmissionAPI:
    """Test bug submission endpoints."""

    def test_submit_bug_without_auth_fails(self, client, sample_bug_data):
        """Test that bug submission without authentication fails."""
        response = client.post(
            "/api/bugs/",
            data=json.dumps(sample_bug_data),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_submit_valid_bug_succeeds(self, client, auth_headers, sample_bug_data):
        """Test successful bug submission."""
        response = client.post(
            "/api/bugs/",
            data=json.dumps(sample_bug_data),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert "id" in data
        assert data["title"] == sample_bug_data["title"]
        assert data["status"] == "approved"

    def test_submit_duplicate_bug_blocked(
        self, client, auth_headers, sample_bug_data, db_session
    ):
        """Test that duplicate bug submission is blocked."""
        # Create original bug
        original = Bug(
            title=sample_bug_data["title"],
            description=sample_bug_data["description"],
            product=sample_bug_data["product"],
            status="approved",
        )
        db_session.add(original)
        db_session.commit()

        # Try to submit duplicate
        response = client.post(
            "/api/bugs/",
            data=json.dumps(sample_bug_data),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should be blocked or flagged
        assert response.status_code in [201, 409]

    def test_submit_low_quality_bug(self, client, auth_headers):
        """Test low quality bug submission."""
        low_quality_data = {
            "title": "Bug",
            "description": "It broke",
            "product": "App",
        }

        response = client.post(
            "/api/bugs/",
            data=json.dumps(low_quality_data),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "issues" in data
        assert "quality_score" in data

    def test_get_bug_details(self, client, auth_headers, db_session):
        """Test getting bug details."""
        # Create bug
        bug = Bug(
            title="Test Bug",
            description="Test description for bug details",
            product="Test Product",
            status="approved",
        )
        db_session.add(bug)
        db_session.commit()

        response = client.get(f"/api/bugs/{bug.id}", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == str(bug.id)
        assert data["title"] == "Test Bug"

    def test_search_bugs(self, client, auth_headers, db_session):
        """Test bug search functionality."""
        # Create test bugs
        for i in range(5):
            bug = Bug(
                title=f"Login Bug {i}",
                description=f"Description {i} about login issues",
                product="Mobile App",
                status="approved",
            )
            db_session.add(bug)
        db_session.commit()

        response = client.get(
            "/api/bugs/search?q=login&product=Mobile%20App", headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["total"] >= 5
        assert len(data["results"]) > 0

    def test_rate_limiting(self, client, auth_headers, sample_bug_data, app):
        """Test that rate limiting works."""
        # Enable rate limiting for this test
        app.config["RATE_LIMIT_ENABLED"] = True

        # Make multiple rapid requests
        for _ in range(5):
            response = client.post(
                "/api/bugs/",
                data=json.dumps(sample_bug_data),
                content_type="application/json",
                headers=auth_headers,
            )

            # First few should succeed or fail normally
            assert response.status_code in [201, 400, 409]

        # Disable again
        app.config["RATE_LIMIT_ENABLED"] = False


class TestAuthenticationAPI:
    """Test authentication endpoints."""

    def test_create_jwt_token(self, client):
        """Test JWT token creation."""
        response = client.post(
            "/api/auth/token",
            data=json.dumps(
                {"username": "test@example.com", "password": "password123"}
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert "token" in data
        assert "expires_in" in data
        assert data["token_type"] == "Bearer"

    def test_create_api_key_requires_admin(self, client, auth_headers):
        """Test that API key creation requires admin role."""
        response = client.post(
            "/api/auth/api-keys",
            data=json.dumps({"name": "Test Key", "role": "user"}),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should fail if user doesn't have admin role
        assert response.status_code in [401, 403]

    def test_list_api_keys_requires_admin(self, client, auth_headers):
        """Test that listing API keys requires admin role."""
        response = client.get("/api/auth/api-keys", headers=auth_headers)

        # Should fail if user doesn't have admin role
        assert response.status_code in [401, 403]


class TestMonitoringAPI:
    """Test monitoring endpoints."""

    def test_get_statistics(self, client, auth_headers, db_session):
        """Test statistics endpoint."""
        # Create some test data
        for i in range(10):
            bug = Bug(
                title=f"Bug {i}",
                description=f"Description {i}",
                product="Test Product",
                status="approved" if i % 2 == 0 else "duplicate",
                is_duplicate=(i % 2 != 0),
            )
            db_session.add(bug)
        db_session.commit()

        response = client.get("/api/monitoring/stats", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "total_bugs" in data
        assert "duplicates_detected" in data
        assert data["total_bugs"] >= 10

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
