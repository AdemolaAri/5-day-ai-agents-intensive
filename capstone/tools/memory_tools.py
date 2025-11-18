"""
Memory Bank tools for AgentFleet agents.

This module provides tool functions for querying and storing incident memories,
designed to be registered with ADK agents.
"""

from typing import List, Dict, Any, Optional
from capstone.memory_bank import get_memory_bank, IncidentMemory


def query_memory_bank(
    query_text: str,
    top_k: int = 5,
    min_similarity: float = 0.5
) -> Dict[str, Any]:
    """
    Query the Memory Bank for similar historical incidents.
    
    This tool performs semantic similarity search to find incidents similar
    to the query text. Results are returned with similarity scores and
    incident details.
    
    Args:
        query_text: Text describing the incident to search for
        top_k: Maximum number of results to return (default: 5)
        min_similarity: Minimum similarity threshold 0.0-1.0 (default: 0.5)
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if query succeeded
        - results: List of similar incidents with scores
        - count: Number of results found
        - error: Error message if query failed
        
    Example:
        >>> result = query_memory_bank("flooding in downtown area", top_k=3)
        >>> print(f"Found {result['count']} similar incidents")
    """
    try:
        memory_bank = get_memory_bank()
        
        # Query with 500ms timeout as per requirements
        similar_incidents = memory_bank.query_similar_incidents(
            query_text=query_text,
            top_k=top_k,
            min_similarity=min_similarity,
            timeout_ms=500
        )
        
        # Format results
        results = []
        for memory, similarity in similar_incidents:
            results.append({
                "incident_id": memory.incident_id,
                "summary": memory.summary,
                "similarity_score": round(similarity, 3),
                "severity": memory.severity,
                "location": memory.location,
                "timestamp": memory.timestamp.isoformat(),
                "metadata": memory.metadata
            })
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "query": query_text
        }
        
    except Exception as e:
        return {
            "success": False,
            "results": [],
            "count": 0,
            "error": str(e)
        }


def store_incident_memory(
    incident_id: str,
    summary: str,
    severity: str,
    location: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Store an incident in the Memory Bank for future pattern recognition.
    
    This tool stores incident summaries with vector embeddings for later
    similarity search. Should be called after incident processing is complete.
    
    Args:
        incident_id: Unique identifier for the incident
        summary: Brief summary of the incident (used for embedding)
        severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
        location: Incident location (optional)
        metadata: Additional metadata to store (optional)
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if storage succeeded
        - incident_id: The stored incident ID
        - message: Success or error message
        
    Example:
        >>> result = store_incident_memory(
        ...     incident_id="inc_123",
        ...     summary="Major flooding in downtown area",
        ...     severity="HIGH",
        ...     location="Downtown District"
        ... )
        >>> print(result['message'])
    """
    try:
        memory_bank = get_memory_bank()
        
        success = memory_bank.store_incident(
            incident_id=incident_id,
            summary=summary,
            severity=severity,
            location=location,
            metadata=metadata
        )
        
        if success:
            return {
                "success": True,
                "incident_id": incident_id,
                "message": f"Incident {incident_id} stored successfully in Memory Bank"
            }
        else:
            return {
                "success": False,
                "incident_id": incident_id,
                "message": "Failed to store incident in Memory Bank"
            }
            
    except Exception as e:
        return {
            "success": False,
            "incident_id": incident_id,
            "message": f"Error storing incident: {str(e)}"
        }


def get_memory_bank_stats() -> Dict[str, Any]:
    """
    Get statistics about the Memory Bank.
    
    Returns information about the number of stored incidents and index status.
    Useful for monitoring and debugging.
    
    Returns:
        Dictionary containing:
        - success: Boolean indicating if stats retrieval succeeded
        - stats: Dictionary with Memory Bank statistics
        - error: Error message if retrieval failed
        
    Example:
        >>> result = get_memory_bank_stats()
        >>> print(f"Total incidents: {result['stats']['total_incidents']}")
    """
    try:
        memory_bank = get_memory_bank()
        stats = memory_bank.get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        return {
            "success": False,
            "stats": {},
            "error": str(e)
        }


def retrieve_incident_by_id(incident_id: str) -> Dict[str, Any]:
    """
    Retrieve a specific incident from Memory Bank by ID.
    
    Args:
        incident_id: Unique identifier for the incident
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if retrieval succeeded
        - incident: Incident details if found
        - error: Error message if not found or failed
        
    Example:
        >>> result = retrieve_incident_by_id("inc_123")
        >>> if result['success']:
        ...     print(result['incident']['summary'])
    """
    try:
        memory_bank = get_memory_bank()
        memory = memory_bank.get_incident_by_id(incident_id)
        
        if memory:
            return {
                "success": True,
                "incident": memory.to_dict()
            }
        else:
            return {
                "success": False,
                "error": f"Incident {incident_id} not found in Memory Bank"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Tool registry for easy agent integration
MEMORY_TOOLS = {
    "query_memory_bank": query_memory_bank,
    "store_incident_memory": store_incident_memory,
    "get_memory_bank_stats": get_memory_bank_stats,
    "retrieve_incident_by_id": retrieve_incident_by_id
}
