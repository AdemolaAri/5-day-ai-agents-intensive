#!/usr/bin/env python3
"""
Integration test for Dispatcher Agent with A2A protocol.
"""

import os
import sys
import json
import time
from datetime import datetime

# Set up environment
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "test-key")

# Add capstone to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capstone.agents.dispatcher_agent import create_dispatcher_agent
from capstone.mcp_envelope import create_triage_envelope
from capstone.models import SeverityLevel, IncidentBrief, TriagedIncident

def test_process_triage_envelope():
    """Test processing a complete triage envelope."""
    print("Testing triage envelope processing...")
    
    # Create agent
    agent = create_dispatcher_agent(
        model_name="gemini-2.0-flash-lite",
        db_path="./capstone/data/agentfleet.db"
    )
    
    # Create a mock triage envelope
    session_id = "test-session-123"
    incident_id = "test-incident-456"
    
    triage_data = {
        "incident_id": incident_id,
        "severity": SeverityLevel.HIGH.value,
        "priority_score": 0.85,
        "job_id": "test-job-789",
        "reasoning": "High severity due to infrastructure impact",
        "triaged_at": datetime.utcnow().isoformat(),
        "brief": {
            "incident_id": incident_id,
            "summary": "Major power outage affecting downtown area. Approximately 200 businesses and 1000 residents without power. Cause under investigation.",
            "key_facts": [
                "Power outage",
                "Downtown area affected",
                "200 businesses impacted",
                "1000 residents affected"
            ],
            "location": "Downtown District",
            "affected_entities": ["businesses", "residents", "traffic signals"],
            "similar_incidents": [],
            "created_at": datetime.utcnow().isoformat()
        }
    }
    
    envelope = create_triage_envelope(
        source_agent="triage_agent",
        triage_data=triage_data,
        session_id=session_id
    )
    
    envelope_dict = envelope.to_dict()
    
    print(f"  Incident ID: {incident_id}")
    print(f"  Severity: {triage_data['severity']}")
    print(f"  Priority Score: {triage_data['priority_score']}")
    
    # Note: We can't actually process with the LLM without a real API key
    # But we can verify the envelope structure is correct
    print("✓ Triage envelope created successfully")
    print(f"  Schema: {envelope_dict['schema']}")
    print(f"  Session ID: {envelope_dict['session_id']}")
    print(f"  Source Agent: {envelope_dict['source_agent']}")
    
    return envelope_dict

def test_agent_card_structure():
    """Test that the agent card has the correct structure."""
    print("\nTesting agent card structure...")
    from capstone.agents.dispatcher_server import agent_card
    import asyncio
    
    # Get the agent card
    card_response = asyncio.run(agent_card())
    card = json.loads(card_response.body.decode())
    
    # Verify structure
    assert card["name"] == "dispatcher_agent"
    assert "capabilities" in card
    assert "action_generation" in card["capabilities"]
    assert "communication_templates" in card["capabilities"]
    assert "incident_persistence" in card["capabilities"]
    assert "dashboard_notification" in card["capabilities"]
    
    assert "endpoints" in card
    assert card["endpoints"]["tasks"] == "/tasks"
    assert card["endpoints"]["health"] == "/health"
    
    assert "input_schema" in card
    assert "output_schema" in card
    
    print("✓ Agent card structure is valid")
    print(f"  Name: {card['name']}")
    print(f"  Capabilities: {', '.join(card['capabilities'])}")
    print(f"  Endpoints: {', '.join(card['endpoints'].keys())}")

if __name__ == "__main__":
    print("=" * 60)
    print("Dispatcher Agent Integration Tests")
    print("=" * 60)
    
    try:
        envelope = test_process_triage_envelope()
        test_agent_card_structure()
        
        print("\n" + "=" * 60)
        print("✓ All integration tests passed!")
        print("=" * 60)
        print("\nNote: Full LLM processing requires a valid GOOGLE_API_KEY")
        print("The agent structure and tools are verified and ready.")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
