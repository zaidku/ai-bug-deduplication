"""
Duplicate detection orchestration logic
"""
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime

from app import db
from app.models.bug import Bug
from app.models.duplicate import DuplicateHistory, LowQualityQueue
from app.models.audit import AuditLog
from app.services.embedding_service import EmbeddingService
from app.services.similarity_engine import SimilarityEngine
from app.services.quality_checker import QualityChecker
from app.utils.vector_store import VectorStore

logger = logging.getLogger(__name__)

class DuplicateDetector:
    """Main orchestrator for duplicate detection and classification"""
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_engine: SimilarityEngine,
        quality_checker: QualityChecker,
        vector_store: VectorStore,
        similarity_threshold: float = 0.85,
        low_confidence_threshold: float = 0.70
    ):
        """
        Initialize duplicate detector
        
        Args:
            embedding_service: Service for generating embeddings
            similarity_engine: Engine for computing similarity
            quality_checker: Checker for bug quality
            vector_store: Vector store for similarity search
            similarity_threshold: Threshold for blocking duplicates
            low_confidence_threshold: Threshold for flagging low confidence matches
        """
        self.embedding_service = embedding_service
        self.similarity_engine = similarity_engine
        self.quality_checker = quality_checker
        self.vector_store = vector_store
        self.similarity_threshold = similarity_threshold
        self.low_confidence_threshold = low_confidence_threshold
    
    def process_incoming_bug(self, bug_data: Dict) -> Tuple[Optional[Bug], str, Dict]:
        """
        Process an incoming bug submission
        
        Args:
            bug_data: Dictionary containing bug information
            
        Returns:
            Tuple of (created_bug_or_none, action_taken, metadata)
            Actions: 'created', 'blocked_duplicate', 'low_quality', 'flagged_for_review'
        """
        reporter = bug_data.get('reporter', 'unknown')
        
        # Step 1: Check quality
        is_quality_ok, quality_issues = self.quality_checker.check_quality(bug_data)
        
        if not is_quality_ok:
            logger.info(f"Bug submission from {reporter} failed quality check: {quality_issues}")
            return self._handle_low_quality(bug_data, quality_issues)
        
        # Step 2: Check for duplicates
        similar_bugs = self.similarity_engine.find_similar_bugs(
            bug_data,
            threshold=self.low_confidence_threshold,  # Use lower threshold for detection
            top_k=10
        )
        
        if similar_bugs:
            best_match = similar_bugs[0]
            match_score = best_match['hybrid_score']
            
            logger.info(
                f"Found similar bug: ID={best_match['bug_id']}, score={match_score:.3f}"
            )
            
            # High confidence duplicate - block creation
            if match_score >= self.similarity_threshold:
                return self._handle_duplicate(bug_data, best_match, blocked=True)
            
            # Medium confidence - create but flag
            elif match_score >= self.low_confidence_threshold:
                return self._handle_duplicate(bug_data, best_match, blocked=False)
        
        # Step 3: No duplicates found - create new bug
        return self._create_new_bug(bug_data)
    
    def _handle_low_quality(
        self,
        bug_data: Dict,
        quality_issues: list
    ) -> Tuple[None, str, Dict]:
        """
        Handle low quality bug submission
        
        Args:
            bug_data: Bug submission data
            quality_issues: List of quality issues
            
        Returns:
            Tuple indicating low quality routing
        """
        # Add to low quality queue
        low_quality_entry = LowQualityQueue(
            title=bug_data.get('title', 'Untitled'),
            description=bug_data.get('description'),
            repro_steps=bug_data.get('repro_steps'),
            logs=bug_data.get('logs'),
            reporter=bug_data.get('reporter'),
            device=bug_data.get('device'),
            build_version=bug_data.get('build_version'),
            region=bug_data.get('region'),
            quality_issues=quality_issues,
            status='Pending'
        )
        
        db.session.add(low_quality_entry)
        
        # Log to audit
        audit = AuditLog(
            event_type='low_quality_flagged',
            low_quality_id=low_quality_entry.id,
            user=bug_data.get('reporter'),
            ai_reasoning={'quality_issues': quality_issues},
            metadata={'bug_data': bug_data}
        )
        db.session.add(audit)
        
        db.session.commit()
        
        logger.info(f"Bug routed to low quality queue: {low_quality_entry.id}")
        
        return None, 'low_quality', {
            'low_quality_id': low_quality_entry.id,
            'issues': quality_issues
        }
    
    def _handle_duplicate(
        self,
        bug_data: Dict,
        match: Dict,
        blocked: bool
    ) -> Tuple[Optional[Bug], str, Dict]:
        """
        Handle duplicate bug detection
        
        Args:
            bug_data: Bug submission data
            match: Best matching bug
            blocked: Whether to block creation
            
        Returns:
            Tuple with result information
        """
        parent_bug = match['bug']
        match_score = match['hybrid_score']
        
        if blocked:
            # Block creation - only record in history
            history = DuplicateHistory(
                duplicate_bug_id=None,
                parent_bug_id=parent_bug.id,
                match_score=match_score,
                match_method='hybrid',
                submission_data=bug_data,
                submitted_by=bug_data.get('reporter'),
                was_blocked=True
            )
            
            db.session.add(history)
            
            # Log to audit
            audit = AuditLog(
                event_type='duplicate_blocked',
                parent_bug_id=parent_bug.id,
                user=bug_data.get('reporter'),
                ai_confidence=match_score,
                ai_reasoning={
                    'match_details': match['match_details'],
                    'threshold': self.similarity_threshold
                },
                metadata={'bug_data': bug_data}
            )
            db.session.add(audit)
            
            db.session.commit()
            
            logger.info(f"Blocked duplicate submission (parent: {parent_bug.id}, score: {match_score:.3f})")
            
            return None, 'blocked_duplicate', {
                'parent_bug_id': parent_bug.id,
                'parent_bug_title': parent_bug.title,
                'match_score': match_score,
                'match_details': match['match_details']
            }
        
        else:
            # Create bug but mark as duplicate
            bug = self._create_bug_from_data(bug_data)
            bug.parent_bug_id = parent_bug.id
            bug.match_score = match_score
            bug.classification_tag = 'Duplicate'
            
            db.session.add(bug)
            db.session.flush()  # Get bug ID
            
            # Record in history
            history = DuplicateHistory(
                duplicate_bug_id=bug.id,
                parent_bug_id=parent_bug.id,
                match_score=match_score,
                match_method='hybrid',
                submission_data=bug_data,
                submitted_by=bug_data.get('reporter'),
                was_blocked=False
            )
            db.session.add(history)
            
            # Log to audit
            audit = AuditLog(
                event_type='duplicate_detected',
                bug_id=bug.id,
                parent_bug_id=parent_bug.id,
                user=bug_data.get('reporter'),
                ai_confidence=match_score,
                ai_reasoning={'match_details': match['match_details']},
                metadata={'bug_data': bug_data}
            )
            db.session.add(audit)
            
            db.session.commit()
            
            logger.info(f"Created duplicate bug {bug.id} (parent: {parent_bug.id}, score: {match_score:.3f})")
            
            return bug, 'flagged_for_review', {
                'bug_id': bug.id,
                'parent_bug_id': parent_bug.id,
                'match_score': match_score,
                'classification': 'Duplicate'
            }
    
    def _create_new_bug(self, bug_data: Dict) -> Tuple[Bug, str, Dict]:
        """
        Create a new bug (no duplicates found)
        
        Args:
            bug_data: Bug submission data
            
        Returns:
            Tuple with created bug and metadata
        """
        bug = self._create_bug_from_data(bug_data)
        db.session.add(bug)
        db.session.flush()
        
        # Generate and store embedding
        text = bug.get_text_for_embedding()
        embedding = self.embedding_service.generate_embedding(text)
        bug.embedding = embedding.tolist()
        
        # Add to vector store
        self.vector_store.add_vectors(embedding.reshape(1, -1), [bug.id])
        
        # Log creation
        audit = AuditLog(
            event_type='bug_created',
            bug_id=bug.id,
            user=bug_data.get('reporter'),
            metadata={'bug_data': bug_data}
        )
        db.session.add(audit)
        
        db.session.commit()
        
        logger.info(f"Created new bug {bug.id}")
        
        return bug, 'created', {'bug_id': bug.id}
    
    def _create_bug_from_data(self, bug_data: Dict) -> Bug:
        """Create a Bug object from submission data"""
        return Bug(
            title=bug_data.get('title'),
            description=bug_data.get('description'),
            repro_steps=bug_data.get('repro_steps'),
            logs=bug_data.get('logs'),
            severity=bug_data.get('severity'),
            priority=bug_data.get('priority'),
            reporter=bug_data.get('reporter'),
            device=bug_data.get('device'),
            os_version=bug_data.get('os_version'),
            build_version=bug_data.get('build_version'),
            region=bug_data.get('region'),
            status='New'
        )
    
    def check_recurring_pattern(self, bug: Bug) -> bool:
        """
        Check if a bug represents a recurring defect
        
        Args:
            bug: Bug to check
            
        Returns:
            True if bug is recurring
        """
        if not bug.parent_bug_id:
            return False
        
        # Count duplicates of the parent bug
        duplicate_count = Bug.query.filter_by(parent_bug_id=bug.parent_bug_id).count()
        
        # If parent has multiple duplicates, mark as recurring
        if duplicate_count >= 3:
            bug.classification_tag = 'Recurring'
            
            # Update parent as well
            parent = Bug.query.get(bug.parent_bug_id)
            if parent:
                parent.classification_tag = 'Recurring'
            
            db.session.commit()
            
            logger.info(f"Marked bug {bug.id} and parent {bug.parent_bug_id} as Recurring")
            return True
        
        return False
