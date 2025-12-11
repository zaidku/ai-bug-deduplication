"""
Embedding service for generating vector representations of bugs
"""
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating embeddings from text"""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the embedding service
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.dimension}")
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text to embed
            
        Returns:
            Numpy array containing the embedding
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(self.dimension, dtype=np.float32)
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.astype(np.float32)
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts (batch processing)
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            Numpy array of shape (n, dimension) containing the embeddings
        """
        if not texts:
            return np.array([])
        
        # Replace empty strings with a space to avoid errors
        processed_texts = [text if text and text.strip() else ' ' for text in texts]
        
        embeddings = self.model.encode(
            processed_texts,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100
        )
        return embeddings.astype(np.float32)
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Compute cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        
        # Clip to [0, 1] range (cosine similarity is in [-1, 1])
        # We use (similarity + 1) / 2 to map [-1, 1] to [0, 1]
        # Or just max with 0 if we only care about positive similarity
        return float(max(0.0, similarity))
    
    def get_dimension(self) -> int:
        """Get the embedding dimension"""
        return self.dimension
