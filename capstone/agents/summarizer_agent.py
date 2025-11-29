
import logging
import json
from typing import Dict, Any


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_key_facts_tool(
    event_content: str,
    event_data: str
) -> Dict[str, Any]:
    """
    Tool function to extract key facts from event data.
    
    This tool identifies and extracts structured information including:
    - Specific numbers and measurements
    - Named entities (people, organizations, places)
    - Temporal information
    - Causal relationships
    - Impact indicators
    
    Args:
        event_content: The event content text
        event_data: JSON string containing full event data
        
    Returns:
        Dictionary containing extracted key facts
    """
    try:
        # Parse event data
        try:
            data = json.loads(event_data)
        except json.JSONDecodeError:
            data = {}
        
        key_facts = []
        
        # Extract location
        location = data.get("location") or data.get("original_event", {}).get("location")
        if location:
            key_facts.append(f"Location: {location}")
        
        # Extract event type
        event_type = data.get("event_type") or data.get("original_event", {}).get("event_type")
        if event_type and event_type != "unknown":
            key_facts.append(f"Type: {event_type.replace('_', ' ').title()}")
        
        # Extract reliability score
        reliability_score = data.get("reliability_score")
        if reliability_score is not None:
            key_facts.append(f"Reliability: {reliability_score:.2f}")
        
        # Extract entities
        entities = data.get("entities") or data.get("original_event", {}).get("entities", [])
        if entities:
            key_facts.append(f"Affected areas: {', '.join(entities[:3])}")
        
        # Extract numbers from content (casualties, damages, etc.)
        words = event_content.split()
        numbers_found = []
        for i, word in enumerate(words):
            if any(char.isdigit() for char in word):
                # Get context around the number
                context_start = max(0, i - 2)
                context_end = min(len(words), i + 3)
                context = " ".join(words[context_start:context_end])
                numbers_found.append(context)
        
        if numbers_found:
            for num_fact in numbers_found[:2]:  # Limit to 2 numerical facts
                key_facts.append(num_fact)
        
        # Extract verified claims count
        verified_claims = data.get("verified_claims", [])
        if verified_claims:
            verified_count = sum(1 for claim in verified_claims if claim.get("verified", False))
            key_facts.append(f"Verified claims: {verified_count}/{len(verified_claims)}")
        
        logger.info(f"Extracted {len(key_facts)} key facts")
        
        return {
            "success": True,
            "key_facts": key_facts,
            "count": len(key_facts)
        }
    
    except Exception as e:
        logger.error(f"Error extracting key facts: {e}")
        return {
            "success": False,
            "error": str(e),
            "key_facts": []
        }