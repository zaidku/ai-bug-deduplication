"""Load testing with Locust."""

from locust import HttpUser, task, between
import json
import random


class BugSubmissionUser(HttpUser):
    """Simulated user submitting bugs."""

    wait_time = between(1, 3)
    api_key = "bgd_test_load_testing_key"

    def on_start(self):
        """Setup before starting tasks."""
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "X-Environment": "load-test",
            "X-Client-Version": "1.0.0",
        }

    @task(3)
    def submit_bug(self):
        """Submit a new bug (most common operation)."""
        bug_data = {
            "title": f"Load test bug {random.randint(1, 10000)}",
            "description": f"This is a load test bug submission number {random.randint(1, 10000)}. "
            "Testing system performance under load.",
            "product": random.choice(["Mobile App", "Web App", "API"]),
            "component": random.choice(["Auth", "UI", "Backend", "Database"]),
            "severity": random.choice(["critical", "major", "minor", "trivial"]),
            "environment": random.choice(["production", "staging", "development"]),
        }

        self.client.post("/api/bugs/", data=json.dumps(bug_data), headers=self.headers)

    @task(2)
    def search_bugs(self):
        """Search for bugs."""
        query = random.choice(["login", "button", "crash", "error", "performance"])
        self.client.get(f"/api/bugs/search?q={query}&limit=20", headers=self.headers)

    @task(1)
    def get_statistics(self):
        """Get system statistics."""
        self.client.get("/api/monitoring/stats", headers=self.headers)

    @task(1)
    def health_check(self):
        """Check system health."""
        self.client.get("/health")


class ReadOnlyUser(HttpUser):
    """Simulated user only reading data."""

    wait_time = between(0.5, 2)
    api_key = "bgd_test_readonly_key"

    def on_start(self):
        self.headers = {"X-API-Key": self.api_key}

    @task(5)
    def search_bugs(self):
        """Search bugs frequently."""
        query = random.choice(["login", "crash", "error"])
        self.client.get(f"/api/bugs/search?q={query}", headers=self.headers)

    @task(3)
    def get_statistics(self):
        """Check statistics."""
        self.client.get("/api/monitoring/stats", headers=self.headers)

    @task(1)
    def health_check(self):
        """Check health."""
        self.client.get("/health")


"""
Run load tests:

# Install locust
pip install locust

# Run load test
locust -f tests/load/locustfile.py --host=http://localhost:5000

# Open browser to http://localhost:8089
# Configure:
# - Number of users: 100
# - Spawn rate: 10 users/second
# - Host: http://localhost:5000

# Run headless
locust -f tests/load/locustfile.py --host=http://localhost:5000 \
       --users 100 --spawn-rate 10 --run-time 5m --headless

# Results show:
# - Requests/second
# - Response times (p50, p95, p99)
# - Failure rate
# - Concurrent users handled
"""
