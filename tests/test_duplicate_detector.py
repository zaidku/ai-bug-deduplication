"""
Test duplicate detector
"""

import pytest

from app.models.bug import Bug
from app.services.duplicate_detector import DuplicateDetector
from app.services.embedding_service import EmbeddingService
from app.services.quality_checker import QualityChecker
from app.services.similarity_engine import SimilarityEngine
from app.utils.vector_store import VectorStore


def test_create_new_bug(app, client):
    """Test creating a new bug with no duplicates"""
    bug_data = {
        "title": "App crashes on startup",
        "description": "The application crashes immediately when opening on iOS 17",
        "repro_steps": "1. Open app\n2. Observe crash",
        "reporter": "test@example.com",
        "device": "iPhone 14",
        "build_version": "1.0.0",
        "region": "US",
    }

    response = client.post("/api/bugs/", json=bug_data)

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "created"
    assert "bug" in data
    assert data["bug"]["title"] == bug_data["title"]


def test_low_quality_submission(app, client):
    """Test low quality bug submission"""
    bug_data = {"title": "bug", "description": "broken", "reporter": "test@example.com"}

    response = client.post("/api/bugs/", json=bug_data)

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "low_quality"
    assert "issues" in data


def test_quality_checker():
    """Test quality checker"""
    checker = QualityChecker(min_description_length=50)

    # Valid submission
    valid_data = {
        "title": "App crashes on startup in iOS 17",
        "description": "The application crashes immediately when opening. This happens consistently across all devices.",
        "repro_steps": "1. Open app\n2. Observe crash",
        "device": "iPhone 14",
        "build_version": "1.0.0",
        "region": "US",
    }
    is_valid, issues = checker.check_quality(valid_data)
    assert is_valid
    assert len(issues) == 0

    # Invalid submission
    invalid_data = {"title": "bug", "description": "broken"}
    is_valid, issues = checker.check_quality(invalid_data)
    assert not is_valid
    assert len(issues) > 0
