"""
Similarity engine for matching bugs using AI and metadata
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from app.models.bug import Bug
from app.services.embedding_service import EmbeddingService
from app.utils.vector_store import VectorStore
from app import db

logger = logging.getLogger(__name__)

class SimilarityEngine:
    """Engine for computing similarity between bugs"""
    
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        """
        Initialize the similarity engine
        
        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector store for similarity search
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
    
    def find_similar_bugs(
        self,
        incoming_bug_data: Dict,
        threshold: float = 0.85,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Find similar bugs to an incoming bug submission
        
        Args:
            incoming_bug_data: Dictionary containing bug information
            threshold: Minimum similarity threshold
            top_k: Number of top candidates to return
            
        Returns:
            List of similar bugs with scores and metadata
        """
        # Generate text for embedding
        text = self._build_text_for_matching(incoming_bug_data)
        
        # Generate embedding
        embedding = self.embedding_service.generate_embedding(text)
        
        # Search vector store
        vector_candidates = self.vector_store.search(embedding, k=top_k * 2)
        
        # Fetch bug details and compute hybrid scores
        candidates = []
        for bug_id, vector_score in vector_candidates:
            bug = Bug.query.get(bug_id)
            if bug is None:
                continue
            
            # Skip resolved/closed bugs unless they're marked as recurring
            if bug.status in ['Resolved', 'Closed'] and bug.classification_tag != 'Recurring':
                continue
            
            # Compute metadata similarity
            metadata_score = self._compute_metadata_similarity(incoming_bug_data, bug)
            
            # Compute hybrid score (weighted combination)
            hybrid_score = self._compute_hybrid_score(
                vector_score,
                metadata_score,
                vector_weight=0.7,
                metadata_weight=0.3
            )
            
            # Apply cross-region normalization if needed
            if self._is_cross_region(incoming_bug_data, bug):
                hybrid_score = self._normalize_cross_region_score(hybrid_score)
            
            if hybrid_score >= threshold * 0.8:  # Lower threshold for initial candidates
                candidates.append({
                    'bug_id': bug.id,
                    'bug': bug,
                    'vector_score': vector_score,
                    'metadata_score': metadata_score,
                    'hybrid_score': hybrid_score,
                    'is_cross_region': self._is_cross_region(incoming_bug_data, bug),
                    'match_details': self._get_match_details(incoming_bug_data, bug)
                })
        
        # Sort by hybrid score
        candidates.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # Return top candidates above threshold
        return [c for c in candidates[:top_k] if c['hybrid_score'] >= threshold]
    
    def _build_text_for_matching(self, bug_data: Dict) -> str:
        """Build combined text from bug data for embedding"""
        parts = [
            bug_data.get('title', ''),
            bug_data.get('description', ''),
            bug_data.get('repro_steps', ''),
            f"Device: {bug_data.get('device', '')}" if bug_data.get('device') else '',
            f"Build: {bug_data.get('build_version', '')}" if bug_data.get('build_version') else '',
            f"Region: {bug_data.get('region', '')}" if bug_data.get('region') else ''
        ]
        return ' '.join(filter(None, parts))
    
    def _compute_metadata_similarity(self, incoming_data: Dict, existing_bug: Bug) -> float:
        """
        Compute similarity based on metadata fields
        
        Args:
            incoming_data: Incoming bug data
            existing_bug: Existing bug from database
            
        Returns:
            Metadata similarity score between 0 and 1
        """
        score = 0.0
        total_weight = 0.0
        
        # Device match (weight: 0.2)
        if incoming_data.get('device') and existing_bug.device:
            if incoming_data['device'].lower() == existing_bug.device.lower():
                score += 0.2
            total_weight += 0.2
        
        # Build version match (weight: 0.3)
        if incoming_data.get('build_version') and existing_bug.build_version:
            if incoming_data['build_version'] == existing_bug.build_version:
                score += 0.3
            elif self._is_similar_build(incoming_data['build_version'], existing_bug.build_version):
                score += 0.15
            total_weight += 0.3
        
        # Region match (weight: 0.2)
        if incoming_data.get('region') and existing_bug.region:
            if incoming_data['region'] == existing_bug.region:
                score += 0.2
            total_weight += 0.2
        
        # OS version match (weight: 0.15)
        if incoming_data.get('os_version') and existing_bug.os_version:
            if incoming_data['os_version'] == existing_bug.os_version:
                score += 0.15
            total_weight += 0.15
        
        # Severity match (weight: 0.15)
        if incoming_data.get('severity') and existing_bug.severity:
            if incoming_data['severity'] == existing_bug.severity:
                score += 0.15
            total_weight += 0.15
        
        # Normalize by total weight
        return score / total_weight if total_weight > 0 else 0.0
    
    def _is_similar_build(self, build1: str, build2: str) -> bool:
        """Check if two build versions are similar (e.g., 1.2.3 vs 1.2.4)"""
        try:
            parts1 = build1.split('.')
            parts2 = build2.split('.')
            
            # Check if major.minor versions match
            if len(parts1) >= 2 and len(parts2) >= 2:
                return parts1[0] == parts2[0] and parts1[1] == parts2[1]
        except:
            pass
        return False
    
    def _compute_hybrid_score(
        self,
        vector_score: float,
        metadata_score: float,
        vector_weight: float = 0.7,
        metadata_weight: float = 0.3
    ) -> float:
        """
        Compute weighted hybrid score
        
        Args:
            vector_score: Embedding similarity score
            metadata_score: Metadata similarity score
            vector_weight: Weight for vector score
            metadata_weight: Weight for metadata score
            
        Returns:
            Combined score
        """
        return (vector_score * vector_weight) + (metadata_score * metadata_weight)
    
    def _is_cross_region(self, incoming_data: Dict, existing_bug: Bug) -> bool:
        """Check if bugs are from different regions"""
        incoming_region = incoming_data.get('region', '').upper()
        existing_region = (existing_bug.region or '').upper()
        
        if not incoming_region or not existing_region:
            return False
        
        return incoming_region != existing_region
    
    def _normalize_cross_region_score(self, score: float, penalty: float = 0.05) -> float:
        """
        Apply normalization for cross-region matches
        
        Args:
            score: Original similarity score
            penalty: Penalty to apply for cross-region matches
            
        Returns:
            Adjusted score
        """
        # Slight penalty for cross-region matches
        return max(0.0, score - penalty)
    
    def _get_match_details(self, incoming_data: Dict, existing_bug: Bug) -> Dict:
        """
        Get detailed match information
        
        Args:
            incoming_data: Incoming bug data
            existing_bug: Existing bug
            
        Returns:
            Dictionary with match details
        """
        return {
            'matching_fields': self._get_matching_fields(incoming_data, existing_bug),
            'differing_fields': self._get_differing_fields(incoming_data, existing_bug),
            'confidence_level': self._determine_confidence_level(incoming_data, existing_bug)
        }
    
    def _get_matching_fields(self, incoming_data: Dict, existing_bug: Bug) -> List[str]:
        """Get list of fields that match between bugs"""
        matching = []
        
        field_map = {
            'device': existing_bug.device,
            'build_version': existing_bug.build_version,
            'region': existing_bug.region,
            'os_version': existing_bug.os_version,
            'severity': existing_bug.severity
        }
        
        for field, existing_value in field_map.items():
            incoming_value = incoming_data.get(field)
            if incoming_value and existing_value and str(incoming_value).lower() == str(existing_value).lower():
                matching.append(field)
        
        return matching
    
    def _get_differing_fields(self, incoming_data: Dict, existing_bug: Bug) -> List[str]:
        """Get list of fields that differ between bugs"""
        differing = []
        
        field_map = {
            'device': existing_bug.device,
            'build_version': existing_bug.build_version,
            'region': existing_bug.region,
            'os_version': existing_bug.os_version
        }
        
        for field, existing_value in field_map.items():
            incoming_value = incoming_data.get(field)
            if incoming_value and existing_value and str(incoming_value).lower() != str(existing_value).lower():
                differing.append(field)
        
        return differing
    
    def _determine_confidence_level(self, incoming_data: Dict, existing_bug: Bug) -> str:
        """
        Determine confidence level of the match
        
        Returns:
            'high', 'medium', or 'low'
        """
        matching = self._get_matching_fields(incoming_data, existing_bug)
        
        # High confidence: many matching fields
        if len(matching) >= 3:
            return 'high'
        # Medium confidence: some matching fields
        elif len(matching) >= 1:
            return 'medium'
        # Low confidence: few or no matching fields
        else:
            return 'low'
