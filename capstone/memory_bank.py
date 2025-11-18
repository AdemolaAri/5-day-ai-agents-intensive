"""
Memory Bank for AgentFleet incident response system.

This module provides vector storage and similarity search capabilities for
incident history, enabling pattern recognition and historical context retrieval.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
import time
import os
from google import genai


@dataclass
class IncidentMemory:
    """
    Stored incident memory with vector embedding.
    
    Attributes:
        incident_id: Unique incident identifier
        summary: Incident summary text
        embedding: Vector embedding of the summary
        severity: Incident severity level
        location: Incident location
        timestamp: When incident was stored
        metadata: Additional incident metadata
    """
    incident_id: str
    summary: str
    embedding: np.ndarray
    severity: str
    location: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (excluding embedding for readability)."""
        return {
            "incident_id": self.incident_id,
            "summary": self.summary,
            "severity": self.severity,
            "location": self.location,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class MemoryBank:
    """
    In-memory vector store for incident history with similarity search.
    
    Uses Gemini embeddings for vector generation and numpy for efficient
    similarity search operations.
    """
    
    def __init__(self, embedding_model: str = "models/text-embedding-004"):
        """
        Initialize Memory Bank.
        
        Args:
            embedding_model: Gemini embedding model to use
        """
        self.embedding_model = embedding_model
        self.memories: List[IncidentMemory] = []
        self.index: Optional[np.ndarray] = None
        self.lock = threading.Lock()
        
        # Initialize Gemini client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        
    def _generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for text using Gemini.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as numpy array
        """
        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text
            )
            
            # Extract embedding from response
            if hasattr(response, 'embeddings') and len(response.embeddings) > 0:
                embedding = response.embeddings[0]
                if hasattr(embedding, 'values'):
                    return np.array(embedding.values, dtype=np.float32)
            
            # Fallback: try direct access
            if hasattr(response, 'embedding'):
                return np.array(response.embedding, dtype=np.float32)
                
            raise ValueError("Could not extract embedding from response")
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}")
    
    def _rebuild_index(self):
        """
        Rebuild the vector index from stored memories.
        
        Creates a numpy array of all embeddings for efficient similarity search.
        """
        if not self.memories:
            self.index = None
            return
        
        # Stack all embeddings into a matrix
        embeddings = [memory.embedding for memory in self.memories]
        self.index = np.vstack(embeddings)
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
        
        # Calculate cosine similarity
        similarity = np.dot(vec1_norm, vec2_norm)
        
        # Ensure result is in [0, 1] range
        return float(max(0.0, min(1.0, (similarity + 1.0) / 2.0)))
    
    def store_incident(
        self,
        incident_id: str,
        summary: str,
        severity: str,
        location: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store an incident in the Memory Bank.
        
        Args:
            incident_id: Unique incident identifier
            summary: Incident summary text
            severity: Incident severity level
            location: Incident location
            metadata: Additional metadata
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Generate embedding for the summary
            embedding = self._generate_embedding(summary)
            
            # Create memory entry
            memory = IncidentMemory(
                incident_id=incident_id,
                summary=summary,
                embedding=embedding,
                severity=severity,
                location=location,
                metadata=metadata or {}
            )
            
            # Store with thread safety
            with self.lock:
                self.memories.append(memory)
                self._rebuild_index()
            
            return True
            
        except Exception as e:
            print(f"Error storing incident in Memory Bank: {e}")
            return False
    
    def query_similar_incidents(
        self,
        query_text: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        timeout_ms: int = 500
    ) -> List[Tuple[IncidentMemory, float]]:
        """
        Query for similar incidents using semantic similarity search.
        
        Args:
            query_text: Query text to search for
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold (0.0 to 1.0)
            timeout_ms: Query timeout in milliseconds
            
        Returns:
            List of (IncidentMemory, similarity_score) tuples, sorted by similarity
        """
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0
        
        try:
            # Check if we have any memories
            with self.lock:
                if not self.memories or self.index is None:
                    return []
                
                # Generate query embedding
                query_embedding = self._generate_embedding(query_text)
                
                # Check timeout
                if time.time() - start_time > timeout_sec:
                    print(f"Query timeout exceeded during embedding generation")
                    return []
                
                # Calculate similarities for all stored incidents
                similarities = []
                for i, memory in enumerate(self.memories):
                    similarity = self._cosine_similarity(query_embedding, memory.embedding)
                    
                    # Only include if above threshold
                    if similarity >= min_similarity:
                        similarities.append((memory, similarity))
                    
                    # Check timeout periodically
                    if i % 10 == 0 and time.time() - start_time > timeout_sec:
                        print(f"Query timeout exceeded during similarity calculation")
                        break
                
                # Sort by similarity (descending) and return top_k
                similarities.sort(key=lambda x: x[1], reverse=True)
                return similarities[:top_k]
                
        except Exception as e:
            print(f"Error querying Memory Bank: {e}")
            return []
    
    def get_incident_by_id(self, incident_id: str) -> Optional[IncidentMemory]:
        """
        Retrieve a specific incident by ID.
        
        Args:
            incident_id: Incident identifier
            
        Returns:
            IncidentMemory if found, None otherwise
        """
        with self.lock:
            for memory in self.memories:
                if memory.incident_id == incident_id:
                    return memory
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get Memory Bank statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self.lock:
            return {
                "total_incidents": len(self.memories),
                "index_size": self.index.shape if self.index is not None else None,
                "embedding_dimension": self.memories[0].embedding.shape[0] if self.memories else None
            }
    
    def clear(self):
        """Clear all stored memories (useful for testing)."""
        with self.lock:
            self.memories.clear()
            self.index = None


# Global Memory Bank instance
_memory_bank_instance: Optional[MemoryBank] = None
_memory_bank_lock = threading.Lock()


def get_memory_bank() -> MemoryBank:
    """
    Get or create the global Memory Bank instance.
    
    Returns:
        Global MemoryBank instance
    """
    global _memory_bank_instance
    
    with _memory_bank_lock:
        if _memory_bank_instance is None:
            _memory_bank_instance = MemoryBank()
        return _memory_bank_instance
