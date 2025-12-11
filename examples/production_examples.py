"""Example showing all production features in action."""

from flask import Flask
from app import create_app, db
from app.models.auth import APIKey
from app.models.bug import Bug
import requests
import time


def example_1_create_api_key():
    """Example 1: Create API key for portal integration."""
    app = create_app()

    with app.app_context():
        # Create API key
        api_key = APIKey.create_key(
            name="Production Portal Integration",
            role="integration",
            expires_in_days=365,
        )

        db.session.add(api_key)
        db.session.commit()

        print(f"API Key created: {api_key.id}")
        print(f"  Name: {api_key.name}")
        print(f"  Role: {api_key.role}")
        print(f"  Expires: {api_key.expires_at}")


def example_2_submit_bug_with_auth():
    """Example 2: Submit bug with authentication."""
    # This would be done from your portal
    api_key = "bgd_live_your_api_key_here"

    bug_data = {
        "title": "Login button not responding on mobile Safari",
        "description": "When users tap the login button on iOS Safari 16.1, "
        "the application does not respond. This is a production issue "
        "affecting multiple users.",
        "product": "Mobile App",
        "component": "Authentication",
        "version": "2.1.0",
        "severity": "major",
        "environment": "production",
        "reporter_email": "qa@yourcompany.com",
        "steps_to_reproduce": [
            "Open mobile app on iOS device with Safari 16.1",
            "Navigate to login page",
            "Enter valid credentials",
            "Tap login button",
            "Observe: No response",
        ],
        "expected_result": "User is authenticated and redirected to dashboard",
        "actual_result": "Button does not respond, user remains on login page",
        "tags": ["mobile", "ios", "authentication", "production"],
    }

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "X-Environment": "production",
        "X-Client-Version": "1.0.0",
    }

    response = requests.post(
        "http://localhost:5000/api/bugs/", json=bug_data, headers=headers
    )

    if response.status_code == 201:
        result = response.json()
        print(f"Bug created successfully!")
        print(f"  ID: {result['id']}")
        print(f"  Status: {result['status']}")
        print(f"  Quality Score: {result['quality_score']}")
        print(f"  Is Duplicate: {result['is_duplicate']}")

    elif response.status_code == 409:
        result = response.json()
        print(f"✗ Duplicate bug blocked")
        print(f"  Original Bug: {result['error']['details']['original_bug']['title']}")
        print(f"  Jira Key: {result['error']['details']['original_bug']['jira_key']}")
        print(f"  Similarity: {result['error']['details']['similarity_score']:.2%}")

    elif response.status_code == 400:
        result = response.json()
        print(f"✗ Low quality submission")
        print(f"  Quality Score: {result['quality_score']}")
        print(f"  Issues:")
        for issue in result["issues"]:
            print(f"    - {issue}")


def example_3_handle_webhooks():
    """Example 3: Handle webhook notifications."""
    from flask import request
    import hmac
    import hashlib
    import json

    @app.route("/webhooks/bug-deduplication", methods=["POST"])
    def handle_webhook():
        # Verify signature
        signature = request.headers.get("X-Webhook-Signature")
        payload = request.json
        secret = "your-webhook-secret"

        message = json.dumps(payload, sort_keys=True).encode()
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature.split("=")[1], expected):
            return {"error": "Invalid signature"}, 401

        # Process event
        event_type = payload["event"]

        if event_type == "duplicate.detected":
            print(f"Duplicate detected:")
            print(f"  Bug: {payload['bug']['title']}")
            print(f"  Original: {payload['duplicate_of']['title']}")
            print(f"  Similarity: {payload['similarity_score']:.2%}")

            # Send notification to your team
            # notify_team(payload)

        elif event_type == "duplicate.blocked":
            print(f"Duplicate blocked:")
            print(f"  Bug: {payload['bug']['title']}")
            print(f"  Jira: {payload['duplicate_of']['jira_key']}")

        elif event_type == "bug.low_quality":
            print(f"Low quality bug submitted:")
            print(f"  Bug: {payload['bug']['title']}")
            print(f"  Issues: {', '.join(payload['quality_issues'])}")

        return {"status": "ok"}, 200


def example_4_monitor_system():
    """Example 4: Monitor system metrics."""
    # Prometheus metrics endpoint
    response = requests.get("http://localhost:5000/metrics")

    print("System Metrics:")
    print(response.text[:500])  # Show sample

    # Statistics endpoint
    response = requests.get(
        "http://localhost:5000/api/monitoring/stats",
        headers={"X-API-Key": "your-api-key"},
    )

    stats = response.json()
    print(f"\nStatistics:")
    print(f"  Total Bugs: {stats['total_bugs']}")
    print(f"  Duplicates Detected: {stats['duplicates_detected']}")
    print(f"  Duplicates Blocked: {stats['duplicates_blocked']}")
    print(f"  Avg Quality Score: {stats['avg_quality_score']:.2f}")
    print(f"  Avg Similarity Score: {stats['avg_similarity_score']:.2f}")


def example_5_handle_rate_limiting():
    """Example 5: Handle rate limiting properly."""
    api_key = "your-api-key"
    headers = {"X-API-Key": api_key}

    for i in range(150):  # Try to exceed limit (100/hour)
        response = requests.post(
            "http://localhost:5000/api/bugs/",
            json={"title": f"Test {i}", "description": "Test", "product": "Test"},
            headers=headers,
        )

        if response.status_code == 429:
            # Rate limited
            retry_after = response.headers.get("Retry-After")
            remaining = response.headers.get("X-RateLimit-Remaining")

            print(f"Rate limited!")
            print(f"  Retry after: {retry_after}s")
            print(f"  Remaining requests: {remaining}")

            # Wait and retry
            time.sleep(int(retry_after))

        elif response.status_code == 201:
            # Success
            limit = response.headers.get("X-RateLimit-Limit")
            remaining = response.headers.get("X-RateLimit-Remaining")
            print(f"Request {i+1} succeeded ({remaining}/{limit} remaining)")


def example_6_run_benchmarks():
    """Example 6: Run performance benchmarks."""
    import subprocess

    print("Running benchmarks...")

    # Run benchmarks
    result = subprocess.run(
        ["python", "benchmarks/run_benchmarks.py"], capture_output=True, text=True
    )

    print(result.stdout)

    # Results saved to:
    # - benchmarks/embedding_generation.json
    # - benchmarks/vector_search.json
    # - benchmarks/quality_check.json
    # - benchmarks/duplicate_detection.json


def example_7_load_testing():
    """Example 7: Run load tests."""
    import subprocess

    print("Running load tests with Locust...")

    # Run headless load test
    subprocess.run(
        [
            "locust",
            "-f",
            "tests/load/locustfile.py",
            "--host",
            "http://localhost:5000",
            "--users",
            "100",
            "--spawn-rate",
            "10",
            "--run-time",
            "1m",
            "--headless",
        ]
    )

    # Or open web UI
    # subprocess.run(["locust", "-f", "tests/load/locustfile.py", "--host", "http://localhost:5000"])
    # Then open: http://localhost:8089


if __name__ == "__main__":
    print("Bug Deduplication System - Production Examples\n")

    examples = [
        ("Create API Key", example_1_create_api_key),
        ("Submit Bug with Auth", example_2_submit_bug_with_auth),
        ("Monitor System", example_4_monitor_system),
        ("Run Benchmarks", example_6_run_benchmarks),
    ]

    for name, func in examples:
        print(f"\n{'='*60}")
        print(f"Example: {name}")
        print("=" * 60)
        try:
            func()
        except Exception as e:
            print(f"Error: {e}")
