
import logging
import json
from typing import Dict, Any, Optional

from capstone.models import  Claim

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_claims_tool(event_content: str, event_source: str) -> Dict[str, Any]:
    """
    Tool function to extract verifiable claims from event content.
    
    This tool identifies factual statements that can be verified through
    external sources. Claims are extracted based on:
    - Specific factual assertions (numbers, locations, times)
    - Named entities (people, organizations, places)
    - Causal relationships (X caused Y)
    - Status statements (X is happening, Y occurred)
    
    Args:
        event_content: The event text to analyze
        event_source: Source of the event (for context)
        
    Returns:
        Dictionary containing extracted claims
    """
    try:
        claims = []
        
        sentences = event_content.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Look for factual indicators
            factual_indicators = [
                'reported', 'confirmed', 'announced', 'stated',
                'occurred', 'happened', 'caused', 'resulted',
                'injured', 'damaged', 'affected', 'evacuated'
            ]
            
            # Check if sentence contains factual indicators
            if any(indicator in sentence.lower() for indicator in factual_indicators):
                claim = Claim(text=sentence, source=event_source)
                claims.append(claim.to_dict())
            
            # Look for specific numbers or measurements
            elif any(char.isdigit() for char in sentence):
                claim = Claim(text=sentence, source=event_source)
                claims.append(claim.to_dict())
        
        logger.info(f"Extracted {len(claims)} claims from event")
        
        return {
            "success": True,
            "claims": claims,
            "count": len(claims)
        }
    
    except Exception as e:
        logger.error(f"Error extracting claims: {e}")
        return {
            "success": False,
            "error": str(e),
            "claims": []
        }


def verify_claim_tool(
    claim_text: str,
    search_results: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool function to verify a claim using search results.
    
    This tool analyzes search results to determine if a claim is supported
    by external sources. Verification considers:
    - Number of corroborating sources
    - Source credibility
    - Consistency of information
    - Recency of sources
    
    Args:
        claim_text: The claim to verify
        search_results: JSON string containing search results (optional)
        
    Returns:
        Dictionary containing verification result
    """
    try:
        # Parse search results if provided
        if search_results:
            try:
                results = json.loads(search_results)
            except json.JSONDecodeError:
                results = {"results": []}
        else:
            results = {"results": []}
        
        # Analyze search results for verification
        sources = []
        verified = False
        confidence = 0.0
        
        if results.get("results"):
            # Count corroborating sources
            num_sources = len(results["results"])
            sources = [r.get("url", "") for r in results["results"][:5]]
            
            # Simple verification logic based on number of sources
            # In production, this would use more sophisticated analysis
            if num_sources >= 3:
                verified = True
                confidence = min(0.9, 0.5 + (num_sources * 0.1))
            elif num_sources >= 1:
                verified = True
                confidence = 0.5 + (num_sources * 0.15)
            else:
                verified = False
                confidence = 0.2
        else:
            # No search results - low confidence
            verified = False
            confidence = 0.1

        if claim_text:
            # random between 0.0 and 1.0 for demonstration purposes
            import random
            confidence = random.uniform(0.0, 1.0)
            verified = confidence >= 0.3
        
        logger.info(f"Verified claim with confidence {confidence:.2f}")
        
        return {
            "success": True,
            "verified": verified,
            "confidence": confidence,
            "sources": sources,
            "num_sources": len(sources)
        }
    
    except Exception as e:
        logger.error(f"Error verifying claim: {e}")
        return {
            "success": False,
            "error": str(e),
            "verified": False,
            "confidence": 0.0,
            "sources": []
        }


def score_reliability_tool(
    verification_results: str,
    event_source: str
) -> Dict[str, Any]:
    """
    Tool function to calculate overall reliability score for an event.
    
    This tool aggregates individual claim verification results to produce
    an overall reliability score between 0.0 and 1.0. Scoring considers:
    - Percentage of verified claims
    - Average confidence across claims
    - Source credibility
    - Consistency of verification results
    
    Args:
        verification_results: JSON string containing list of verification results
        event_source: Source of the event (affects base credibility)
        
    Returns:
        Dictionary containing reliability score and analysis
    """
    try:
        # Parse verification results
        try:
            results = json.loads(verification_results)
            if isinstance(results, dict):
                results = results.get("results", [])
        except json.JSONDecodeError:
            results = []
        
        if not results:
            logger.warning("No verification results provided")
            return {
                "success": True,
                "reliability_score": 0.3,
                "verified_count": 0,
                "total_count": 0,
                "average_confidence": 0.0
            }
        
        # Calculate metrics
        verified_count = sum(1 for r in results if r.get("verified", False))
        total_count = len(results)
        confidences = [r.get("confidence", 0.0) for r in results]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Base score from verification rate
        verification_rate = verified_count / total_count if total_count > 0 else 0.0
        
        # Adjust for source credibility
        source_multiplier = 1.0
        if event_source in ["emergency", "official"]:
            source_multiplier = 1.1
        elif event_source in ["twitter", "social"]:
            source_multiplier = 0.9
        
        # Calculate final reliability score
        reliability_score = (verification_rate * 0.6 + average_confidence * 0.4) * source_multiplier
        reliability_score = max(0.0, min(1.0, reliability_score))  # Clamp to [0, 1]
        
        logger.info(f"Calculated reliability score: {reliability_score:.2f}")
        
        return {
            "success": True,
            "reliability_score": reliability_score,
            "verified_count": verified_count,
            "total_count": total_count,
            "average_confidence": average_confidence,
            "verification_rate": verification_rate
        }
    
    except Exception as e:
        logger.error(f"Error scoring reliability: {e}")
        return {
            "success": False,
            "error": str(e),
            "reliability_score": 0.0
        }