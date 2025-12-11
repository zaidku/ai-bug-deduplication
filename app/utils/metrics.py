"""Prometheus metrics exporter for monitoring."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from flask import Response, current_app
from functools import wraps
import time

# Request metrics
request_count = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)

request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

# Bug submission metrics
bug_submissions_total = Counter(
    "bug_submissions_total", "Total bug submissions", ["product", "severity", "status"]
)

duplicate_detections_total = Counter(
    "duplicate_detections_total",
    "Total duplicate bugs detected",
    ["action"],  # blocked, flagged
)

low_quality_bugs_total = Counter(
    "low_quality_bugs_total", "Total low quality bug submissions"
)

quality_score_histogram = Histogram(
    "bug_quality_score",
    "Bug quality score distribution",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

similarity_score_histogram = Histogram(
    "bug_similarity_score",
    "Bug similarity score distribution",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# External integration metrics
jira_sync_total = Counter(
    "jira_sync_total", "Total bugs synced to Jira", ["status"]  # success, failure
)

tp_sync_total = Counter(
    "tp_sync_total",
    "Total bugs synced to Test Platform",
    ["status"],  # success, failure
)

# System metrics
active_bugs = Gauge("active_bugs_total", "Total number of active bugs", ["status"])

api_key_usage = Counter(
    "api_key_usage_total", "API key usage count", ["key_name", "role"]
)

bot_submissions = Counter("bot_submissions_total", "Total bot-detected submissions")

rate_limit_exceeded = Counter(
    "rate_limit_exceeded_total", "Total rate limit violations", ["endpoint"]
)

# Cache metrics
cache_hits = Counter("cache_hits_total", "Total cache hits", ["cache_key"])

cache_misses = Counter("cache_misses_total", "Total cache misses", ["cache_key"])

# Vector store metrics
vector_search_duration = Histogram(
    "vector_search_duration_seconds", "Vector similarity search duration"
)

embedding_generation_duration = Histogram(
    "embedding_generation_duration_seconds", "Embedding generation duration"
)


def track_request_metrics(f):
    """Decorator to track request metrics."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()

        # Execute request
        response = f(*args, **kwargs)

        # Track metrics
        duration = time.time() - start_time

        # Get endpoint and method from Flask request context
        from flask import request

        endpoint = request.endpoint or "unknown"
        method = request.method
        status_code = response.status_code if hasattr(response, "status_code") else 200

        request_count.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()

        request_duration.labels(method=method, endpoint=endpoint).observe(duration)

        return response

    return decorated_function


def track_bug_submission(bug_data, result):
    """Track bug submission metrics."""
    bug_submissions_total.labels(
        product=bug_data.get("product", "unknown"),
        severity=bug_data.get("severity", "unknown"),
        status=result.get("status", "unknown"),
    ).inc()

    # Track quality score
    if quality_score := result.get("quality_score"):
        quality_score_histogram.observe(quality_score)

    # Track duplicate detection
    if result.get("is_duplicate"):
        action = "blocked" if result["status"] == "blocked_duplicate" else "flagged"
        duplicate_detections_total.labels(action=action).inc()

        if similarity_score := result.get("similarity_score"):
            similarity_score_histogram.observe(similarity_score)

    # Track low quality
    if result.get("status") == "low_quality":
        low_quality_bugs_total.inc()

    # Track bot submissions
    if bug_data.get("is_automated"):
        bot_submissions.inc()


def track_jira_sync(success: bool):
    """Track Jira synchronization."""
    status = "success" if success else "failure"
    jira_sync_total.labels(status=status).inc()


def track_tp_sync(success: bool):
    """Track Test Platform synchronization."""
    status = "success" if success else "failure"
    tp_sync_total.labels(status=status).inc()


def track_api_key_usage(key_name: str, role: str):
    """Track API key usage."""
    api_key_usage.labels(key_name=key_name, role=role).inc()


def track_rate_limit(endpoint: str):
    """Track rate limit violations."""
    rate_limit_exceeded.labels(endpoint=endpoint).inc()


def track_cache_hit(cache_key: str):
    """Track cache hit."""
    cache_hits.labels(cache_key=cache_key).inc()


def track_cache_miss(cache_key: str):
    """Track cache miss."""
    cache_misses.labels(cache_key=cache_key).inc()


def track_vector_search(duration: float):
    """Track vector search duration."""
    vector_search_duration.observe(duration)


def track_embedding_generation(duration: float):
    """Track embedding generation duration."""
    embedding_generation_duration.observe(duration)


def update_active_bugs_gauge():
    """Update active bugs gauge from database."""
    from app.models.bug import Bug
    from app import db

    # Count bugs by status
    statuses = ["pending_review", "approved", "rejected", "duplicate", "low_quality"]

    for status in statuses:
        count = Bug.query.filter_by(status=status).count()
        active_bugs.labels(status=status).set(count)


def metrics_endpoint():
    """Prometheus metrics endpoint."""
    # Update gauges before exporting
    try:
        update_active_bugs_gauge()
    except Exception as e:
        current_app.logger.error(f"Failed to update metrics: {e}")

    return Response(generate_latest(REGISTRY), mimetype="text/plain")
