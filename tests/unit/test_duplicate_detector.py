"""Unit tests for duplicate detector."""

import pytest
from unittest.mock import Mock, patch
from app.services.duplicate_detector import DuplicateDetector
from app.services.quality_checker import QualityChecker
from app.services.similarity_engine import SimilarityEngine
from app.models.bug import Bug


class TestDuplicateDetector:
    """Test duplicate detection logic."""

    @pytest.fixture
    def quality_checker(self):
        return QualityChecker(
            min_description_length=20, require_repro_steps=False, require_logs=False
        )

    @pytest.fixture
    def similarity_engine(self):
        mock_embedding = Mock()
        mock_vector_store = Mock()
        return SimilarityEngine(mock_embedding, mock_vector_store)

    @pytest.fixture
    def detector(self, quality_checker, similarity_engine):
        mock_embedding = Mock()
        mock_vector_store = Mock()
        return DuplicateDetector(
            mock_embedding,
            similarity_engine,
            quality_checker,
            mock_vector_store,
            similarity_threshold=0.85,
            low_confidence_threshold=0.70,
        )

    def test_high_quality_bug_passes(self, detector, sample_bug_data):
        """Test that high quality bug passes validation."""
        with patch.object(
            detector.similarity_engine, "find_similar_bugs", return_value=[]
        ):
            result = detector.process_incoming_bug(sample_bug_data)

            assert result["status"] == "approved"
            assert result["bug"] is not None
            assert result["quality_score"] >= 0.6

    def test_low_quality_bug_flagged(self, detector):
        """Test that low quality bug is flagged."""
        low_quality_data = {
            "title": "Bug",
            "description": "It broke",
            "product": "App",
        }

        with patch.object(
            detector.similarity_engine, "find_similar_bugs", return_value=[]
        ):
            result = detector.process_incoming_bug(low_quality_data)

            assert result["status"] == "low_quality"
            assert result["quality_score"] < 0.6
            assert len(result["issues"]) > 0

    def test_high_similarity_blocks_duplicate(
        self, detector, sample_bug_data, db_session
    ):
        """Test that high similarity score blocks duplicate."""
        # Create original bug
        original = Bug(
            title="Login button issue",
            description="Login button not working on iOS",
            product="Mobile App",
            status="approved",
        )
        db_session.add(original)
        db_session.commit()

        # Mock high similarity
        with patch.object(
            detector.similarity_engine,
            "find_similar_bugs",
            return_value=[(original, 0.92)],
        ):
            result = detector.process_incoming_bug(sample_bug_data)

            assert result["status"] == "blocked_duplicate"
            assert result["similarity_score"] >= 0.85
            assert result["duplicate_of"] == original

    def test_medium_similarity_flags_duplicate(
        self, detector, sample_bug_data, db_session
    ):
        """Test that medium similarity creates but flags as duplicate."""
        # Create original bug
        original = Bug(
            title="Login button problem",
            description="Login not functioning properly",
            product="Mobile App",
            status="approved",
        )
        db_session.add(original)
        db_session.commit()

        # Mock medium similarity
        with patch.object(
            detector.similarity_engine,
            "find_similar_bugs",
            return_value=[(original, 0.75)],
        ):
            result = detector.process_incoming_bug(sample_bug_data)

            assert result["status"] == "flagged_duplicate"
            assert 0.70 <= result["similarity_score"] < 0.85
            assert result["bug"].is_duplicate is True
            assert result["bug"].duplicate_of_id == original.id

    def test_recurring_pattern_detection(self, detector, sample_bug_data, db_session):
        """Test detection of recurring bug patterns."""
        # Create original bug with multiple duplicates
        original = Bug(
            title="Login issue",
            description="Login broken",
            product="Mobile App",
            status="approved",
        )
        db_session.add(original)
        db_session.commit()

        # Create 3 duplicates
        for i in range(3):
            dup = Bug(
                title=f"Login duplicate {i}",
                description="Login not working",
                product="Mobile App",
                duplicate_of_id=original.id,
                is_duplicate=True,
            )
            db_session.add(dup)
        db_session.commit()

        # Mock finding original
        with patch.object(
            detector.similarity_engine,
            "find_similar_bugs",
            return_value=[(original, 0.90)],
        ):
            result = detector.process_incoming_bug(sample_bug_data)

            # Should be blocked due to high similarity
            assert result["status"] == "blocked_duplicate"
            # Original should be flagged as recurring
            assert original.is_recurring_issue is True
