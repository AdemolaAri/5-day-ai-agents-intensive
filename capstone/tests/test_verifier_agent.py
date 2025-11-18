"""
Basic tests for Verifier Agent functionality.

These tests verify core functionality of the Verifier Agent:
- Claim extraction from event content
- Claim verification logic
- Reliability scoring
- MCP envelope processing
"""

import json
from datetime import datetime
from capstone.agents.verifier_agent import (
    extract_claims_tool,
    verify_claim_tool,
    score_reliability_tool
)
from capstone.mcp_envelope import create_event_envelope
from capstone.models import NormalizedEvent


def test_extract_claims():
    """Test claim extraction from event content."""
    event_content = "Flooding reported in downtown area. 50 people evacuated. Emergency services confirmed the incident."
    event_source = "twitter"
    
    result = extract_claims_tool(event_content, event_source)
    
    assert result["success"] is True
    assert "claims" in result
    assert result["count"] > 0
    print(f"✓ Extracted {result['count']} claims from event")


def test_verify_claim():
    """Test claim verification logic."""
    claim_text = "50 people evacuated from downtown"
    
    # Test with no search results
    result = verify_claim_tool(claim_text)
    assert result["success"] is True
    assert "verified" in result
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0
    print(f"✓ Verified claim with confidence {result['confidence']:.2f}")
    
    # Test with mock search results
    search_results = json.dumps({
        "results": [
            {"url": "http://example.com/1", "title": "Evacuation confirmed"},
            {"url": "http://example.com/2", "title": "Downtown flooding"},
            {"url": "http://example.com/3", "title": "Emergency response"}
        ]
    })
    
    result = verify_claim_tool(claim_text, search_results)
    assert result["success"] is True
    assert result["verified"] is True
    assert result["confidence"] > 0.5
    print(f"✓ Verified claim with search results: confidence {result['confidence']:.2f}")


def test_score_reliability():
    """Test reliability scoring."""
    # Create mock verification results
    verification_results = json.dumps({
        "results": [
            {"verified": True, "confidence": 0.8},
            {"verified": True, "confidence": 0.9},
            {"verified": False, "confidence": 0.3}
        ]
    })
    
    result = score_reliability_tool(verification_results, "emergency")
    
    assert result["success"] is True
    assert "reliability_score" in result
    assert 0.0 <= result["reliability_score"] <= 1.0
    assert result["verified_count"] == 2
    assert result["total_count"] == 3
    print(f"✓ Calculated reliability score: {result['reliability_score']:.2f}")


def test_envelope_processing():
    """Test MCP envelope creation and parsing."""
    # Create a normalized event
    event = NormalizedEvent(
        event_id="test-123",
        source="twitter",
        timestamp=datetime.utcnow(),
        content="Test flooding event in downtown",
        entities=["downtown"],
        location="downtown",
        event_type="flooding"
    )
    
    # Create envelope
    envelope = create_event_envelope(
        source_agent="ingest_agent",
        event_data=event.to_dict(),
        session_id="test-session-123"
    )
    
    assert envelope.schema == "event_v1"
    assert envelope.source_agent == "ingest_agent"
    assert envelope.session_id == "test-session-123"
    assert envelope.payload["type"] == "event"
    print(f"✓ Created and validated MCP envelope")


if __name__ == "__main__":
    print("Running Verifier Agent tests...\n")
    
    test_extract_claims()
    test_verify_claim()
    test_score_reliability()
    test_envelope_processing()
    
    print("\n✅ All tests passed!")
