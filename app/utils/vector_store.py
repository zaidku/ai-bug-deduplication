"""
Vector store for fast similarity search using FAISS
"""
import faiss
import numpy as np
import pickle
import os
from typing import List, Tuple, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class VectorStore:
    """FAISS-based vector store for similarity search"""
    
    def __init__(self, dimension: int = 384, index_path: str = './data/faiss_index'):
        """
        Initialize the vector store
        
        Args:
            dimension: Dimension of the embedding vectors
            index_path: Path to save/load the FAISS index
        """
        self.dimension = dimension
        self.index_path = index_path
        self.index = None
        self.bug_ids = []  # Maps index positions to bug IDs
        
        # Create directory if it doesn't exist
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load index
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize a new FAISS index or load existing one"""
        if os.path.exists(f"{self.index_path}.index"):
            self.load_index()
        else:
            # Create a new index with Inner Product (for cosine similarity with normalized vectors)
            # Using IndexFlatIP for exact search (can be upgraded to IndexIVFFlat for larger datasets)
            self.index = faiss.IndexFlatIP(self.dimension)
            logger.info(f"Created new FAISS index with dimension {self.dimension}")
    
    def add_vectors(self, embeddings: np.ndarray, bug_ids: List[int]):
        """
        Add vectors to the index
        
        Args:
            embeddings: Array of shape (n, dimension) containing embeddings
            bug_ids: List of bug IDs corresponding to embeddings
        """
        if embeddings.shape[0] != len(bug_ids):
            raise ValueError("Number of embeddings must match number of bug IDs")
        
        # Normalize vectors for cosine similarity
        normalized_embeddings = self._normalize_vectors(embeddings)
        
        # Add to index
        self.index.add(normalized_embeddings)
        self.bug_ids.extend(bug_ids)
        
        logger.info(f"Added {len(bug_ids)} vectors to index. Total: {len(self.bug_ids)}")
    
    def search(self, query_embedding: np.ndarray, k: int = 10) -> List[Tuple[int, float]]:
        """
        Search for similar vectors
        
        Args:
            query_embedding: Query embedding vector
            k: Number of nearest neighbors to return
            
        Returns:
            List of tuples (bug_id, similarity_score)
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Normalize query vector
        normalized_query = self._normalize_vectors(query_embedding.reshape(1, -1))
        
        # Search (k+1 to account for the query itself potentially being in the index)
        search_k = min(k + 1, self.index.ntotal)
        distances, indices = self.index.search(normalized_query, search_k)
        
        # Convert to list of (bug_id, score)
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx != -1 and idx < len(self.bug_ids):
                bug_id = self.bug_ids[idx]
                # Distance is already cosine similarity due to normalized vectors and IP
                similarity_score = float(distance)
                results.append((bug_id, similarity_score))
        
        return results[:k]
    
    def remove_vector(self, bug_id: int):
        """
        Remove a vector from the index (requires rebuild)
        
        Args:
            bug_id: Bug ID to remove
        """
        if bug_id in self.bug_ids:
            self.bug_ids.remove(bug_id)
            logger.info(f"Marked bug {bug_id} for removal. Index rebuild required.")
    
    def rebuild_index(self, embeddings: np.ndarray, bug_ids: List[int]):
        """
        Rebuild the entire index from scratch
        
        Args:
            embeddings: All embeddings to index
            bug_ids: All corresponding bug IDs
        """
        logger.info(f"Rebuilding index with {len(bug_ids)} vectors")
        
        # Create new index
        self.index = faiss.IndexFlatIP(self.dimension)
        self.bug_ids = []
        
        # Add all vectors
        if len(bug_ids) > 0:
            self.add_vectors(embeddings, bug_ids)
        
        # Save the rebuilt index
        self.save_index()
        logger.info("Index rebuild complete")
    
    def save_index(self):
        """Save the FAISS index to disk"""
        if self.index is not None:
            faiss.write_index(self.index, f"{self.index_path}.index")
            
            # Save bug_ids mapping
            with open(f"{self.index_path}.mapping", 'wb') as f:
                pickle.dump(self.bug_ids, f)
            
            logger.info(f"Saved index to {self.index_path}")
    
    def load_index(self):
        """Load the FAISS index from disk"""
        try:
            self.index = faiss.read_index(f"{self.index_path}.index")
            
            # Load bug_ids mapping
            with open(f"{self.index_path}.mapping", 'rb') as f:
                self.bug_ids = pickle.load(f)
            
            logger.info(f"Loaded index from {self.index_path}. Contains {len(self.bug_ids)} vectors")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            self._initialize_index()
    
    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """
        Normalize vectors to unit length (for cosine similarity)
        
        Args:
            vectors: Array of vectors to normalize
            
        Returns:
            Normalized vectors
        """
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid division by zero
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms
    
    def get_stats(self) -> dict:
        """Get statistics about the index"""
        return {
            'total_vectors': len(self.bug_ids),
            'dimension': self.dimension,
            'index_type': type(self.index).__name__ if self.index else None
        }
