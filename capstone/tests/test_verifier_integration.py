"""
Integration test for Verifier Agent A2A communication.

This test verifies that the Verifier Agent can:
- Receive MCP envelopes via A2A protocol
- Process events through the agent pipeline
- Return proper A2A response envelopes
"""

import json
from datetime import datetime
from capstone.agents.verifier_agent import create_verifier_agent
from capstone.mcp_envelope import create_event_envelope
from capstone.models import NormalizedEvent


def test_verifier_agent_envelope_processing():
    """Test that Verifier Agent can process MCP envelopes."""
    print("Testing Verifier Agent envelope processing...")
    
    # Create a test agent (without actual Summarizer connection)
    agent = create_verifier_agent(
        model_name="gemini-2.0-flash-lite",
        summarizer_url="http://localhost:8003"
    )
    
    # Create a test normalized event
    event = NormalizedEvent(
        event_id="test-event-456",
        source="emergency",
        timestamp=datetime.utcnow(),
        content="Major flooding reported in downtown area. Emergency services confirmed 50 people evacuated. Water levels rising rapidly.",
        entities=["downtown area", "emergency services"],
        location="downtown area",
        event_type="flooding"
    )
    
    # Create MCP envelope
    envelope = create_event_envelope(
        source_agent="ingest_agent",
        event_data=event.to_dict(),
        session_id="test-session-456"
    )
    
    # Process envelope through agent
    result = agent.process_event_envelope(envelope.to_dict())
    
    # Verify result
    assert result["success"] is True
    assert "response" in result
    assert result["session_id"] == "test-session-456"
    
    print(f"✓ Agent processed envelope successfully")
    print(f"  Session ID: {result['session_id']}")
    print(f"  Response preview: {result['response'][:100]}...")
    
    return result


def test_claim_extraction_workflow():
    """Test the complete claim extraction and verification workflow."""
    print("\nTesting claim extraction workflow...")
    
    from capstone.agents.verifier_agent import (
        extract_claims_tool,
        verify_claim_tool,
        score_reliability_tool
    )
    
    # Step 1: Extract claims
    event_content = "Flooding reported in downtown. 50 people evacuated. Emergency services on scene."
    claims_result = extract_claims_tool(event_content, "emergency")
    
    assert claims_result["success"] is True
    claims = claims_result["claims"]
    print(f"✓ Extracted {len(claims)} claims")
    
    # Step 2: Verify each claim
    verification_results = []
    for claim in claims:
        verify_result = verify_claim_tool(claim["text"])
        verification_results.append(verify_result)
        print(f"  - Claim verified: {verify_result['verified']} (confidence: {verify_result['confidence']:.2f})")
    
    # Step 3: Score reliability
    score_result = score_reliability_tool(
        json.dumps({"results": verification_results}),
        "emergency"
    )
    
    assert score_result["success"] is True
    print(f"✓ Overall reliability score: {score_result['reliability_score']:.2f}")
    print(f"  Verified: {score_result['verified_count']}/{score_result['total_count']} claims")
    
    return score_result


if __name__ == "__main__":
    print("Running Verifier Agent integration tests...\n")
    print("=" * 60)
    
    # Note: These tests require GOOGLE_API_KEY to be set
    import os
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY not set - skipping agent tests")
        print("   (Tool tests will still run)")
        print()
        test_claim_extraction_workflow()
    else:
        test_verifier_agent_envelope_processing()
        test_claim_extraction_workflow()
    
    print("\n" + "=" * 60)
    print("✅ All integration tests completed!")
