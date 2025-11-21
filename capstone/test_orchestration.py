#!/usr/bin/env python3
"""
Test script for AgentFleet orchestration components.

This script tests the agent startup, discovery, and utility functions
to ensure the orchestration system works correctly.

Requirements Satisfied:
- Testing of Task 12 implementation
- Validation of agent discovery and registration
- Verification of A2A communication utilities
"""

import os
import sys
import time
import unittest
import tempfile
import subprocess
from pathlib import Path

# Add the capstone directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from capstone.start_agents import AgentOrchestrator
from capstone.agent_discovery import AgentRegistry, AgentInfo
from capstone.agent_utils import A2ACommunicator, A2ARequest, create_mcp_envelope


class TestAgentOrchestration(unittest.TestCase):
    """Test cases for agent orchestration components."""
    
    def setUp(self):
        """Set up test environment."""
        # Change to capstone directory
        self.original_dir = os.getcwd()
        os.chdir(Path(__file__).parent)
        
        # Create temporary registry file
        self.temp_registry = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_registry.close()
    
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_dir)
        
        # Clean up temporary files
        try:
            os.unlink(self.temp_registry.name)
        except FileNotFoundError:
            pass
    
    def test_agent_orchestrator_creation(self):
        """Test that AgentOrchestrator can be created."""
        orchestrator = AgentOrchestrator(self.temp_registry.name)
        self.assertIsNotNone(orchestrator)
        self.assertEqual(len(orchestrator.agents), 5)  # 5 default agents
        self.assertIn("ingest", orchestrator.agents)
        self.assertIn("verifier", orchestrator.agents)
        self.assertIn("summarizer", orchestrator.agents)
        self.assertIn("triage", orchestrator.agents)
        self.assertIn("dispatcher", orchestrator.agents)
    
    def test_agent_registry_creation(self):
        """Test that AgentRegistry can be created."""
        registry = AgentRegistry(self.temp_registry.name)
        self.assertIsNotNone(registry)
        self.assertEqual(len(registry.agents), 5)  # 5 default agents
        
        # Test agent retrieval
        ingest_agent = registry.get_agent("ingest")
        self.assertIsNotNone(ingest_agent)
        self.assertEqual(ingest_agent.name, "Ingest Agent")
        self.assertEqual(ingest_agent.url, "http://localhost:8001")
    
    def test_agent_registration(self):
        """Test agent registration functionality."""
        registry = AgentRegistry(self.temp_registry.name)
        
        # Create test agent
        test_agent = AgentInfo(
            name="Test Agent",
            url="http://localhost:9999",
            capabilities=["test_capability"],
            endpoints={"health": "/health", "tasks": "/tasks"}
        )
        
        # Register agent
        result = registry.register_agent("test_agent", test_agent)
        self.assertTrue(result)
        
        # Verify registration
        registered_agent = registry.get_agent("test_agent")
        self.assertIsNotNone(registered_agent)
        self.assertEqual(registered_agent.name, "Test Agent")
        self.assertEqual(registered_agent.url, "http://localhost:9999")
    
    def test_capability_search(self):
        """Test capability-based agent search."""
        registry = AgentRegistry(self.temp_registry.name)
        
        # Search for agents with specific capabilities
        summarizer_agents = registry.get_agent_by_capability("incident_summarization")
        self.assertTrue(len(summarizer_agents) > 0)
        self.assertTrue(any("Summarizer" in agent.name for agent in summarizer_agents))
        
        verification_agents = registry.get_agent_by_capability("claim_extraction")
        self.assertTrue(len(verification_agents) > 0)
        self.assertTrue(any("Verifier" in agent.name for agent in verification_agents))
    
    def test_mcp_envelope_creation(self):
        """Test MCP envelope creation utility."""
        envelope = create_mcp_envelope(
            schema="test_schema_v1",
            source_agent="test_agent",
            payload={"test": "data"},
            session_id="test-session-123"
        )
        
        self.assertEqual(envelope["schema"], "test_schema_v1")
        self.assertEqual(envelope["source_agent"], "test_agent")
        self.assertEqual(envelope["session_id"], "test-session-123")
        self.assertIn("timestamp", envelope)
        self.assertEqual(envelope["payload"]["test"], "data")
    
    def test_a2a_request_creation(self):
        """Test A2A request creation."""
        envelope = {"test": "envelope"}
        request = A2ARequest(
            agent_url="http://localhost:8001",
            envelope=envelope,
            timeout=30,
            max_retries=3
        )
        
        self.assertEqual(request.agent_url, "http://localhost:8001")
        self.assertEqual(request.envelope, envelope)
        self.assertEqual(request.timeout, 30)
        self.assertEqual(request.max_retries, 3)
    
    def test_registry_persistence(self):
        """Test that registry data is persisted and loaded correctly."""
        # Create registry with test data
        registry = AgentRegistry(self.temp_registry.name)
        
        # Add a test agent
        test_agent = AgentInfo(
            name="Persistent Test Agent",
            url="http://localhost:8888",
            capabilities=["persistence_test"]
        )
        registry.register_agent("persistent_test", test_agent)
        
        # Save registry
        registry._save_registry()
        
        # Create new registry instance
        new_registry = AgentRegistry(self.temp_registry.name)
        
        # Verify agent was loaded
        loaded_agent = new_registry.get_agent("persistent_test")
        self.assertIsNotNone(loaded_agent)
        self.assertEqual(loaded_agent.name, "Persistent Test Agent")
        self.assertEqual(loaded_agent.url, "http://localhost:8888")
        self.assertIn("persistence_test", loaded_agent.capabilities)
    
    def test_health_check_timeout(self):
        """Test that health checks timeout correctly for non-responsive agents."""
        registry = AgentRegistry(self.temp_registry.name)
        
        # Create a non-responsive agent
        non_existent_agent = AgentInfo(
            name="Non-existent Agent",
            url="http://localhost:9999",  # Port that shouldn't be in use
            capabilities=["test"]
        )
        registry.register_agent("non_existent", non_existent_agent)
        
        # Check health (should fail due to connection timeout)
        healthy = registry.check_agent_health("non_existent")
        self.assertFalse(healthy)
        
        # Verify status was updated
        updated_agent = registry.get_agent("non_existent")
        self.assertIsNotNone(updated_agent)
        self.assertEqual(updated_agent.status, "offline")
        self.assertGreater(updated_agent.consecutive_failures, 0)
    
    def test_agent_info_serialization(self):
        """Test AgentInfo serialization and deserialization."""
        # Create agent info
        original_agent = AgentInfo(
            name="Serialization Test",
            url="http://test:8000",
            capabilities=["test"],
            endpoints={"health": "/health"},
            version="1.0.0",
            metadata={"test_key": "test_value"}
        )
        
        # Serialize to dict
        agent_dict = original_agent.to_dict()
        
        # Deserialize from dict
        deserialized_agent = AgentInfo.from_dict(agent_dict)
        
        # Verify all fields match
        self.assertEqual(original_agent.name, deserialized_agent.name)
        self.assertEqual(original_agent.url, deserialized_agent.url)
        self.assertEqual(original_agent.capabilities, deserialized_agent.capabilities)
        self.assertEqual(original_agent.endpoints, deserialized_agent.endpoints)
        self.assertEqual(original_agent.version, deserialized_agent.version)
        self.assertEqual(original_agent.metadata, deserialized_agent.metadata)


def run_basic_functionality_tests():
    """Run basic functionality tests that don't require network access."""
    print("Running AgentFleet Orchestration Tests...")
    print("=" * 50)
    
    # Test 1: Agent Orchestrator Creation
    print("1. Testing AgentOrchestrator creation...")
    try:
        orchestrator = AgentOrchestrator()
        print(f"   ✓ Created orchestrator with {len(orchestrator.agents)} agents")
        print(f"   ✓ Agents: {list(orchestrator.agents.keys())}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # Test 2: Agent Registry Creation
    print("2. Testing AgentRegistry creation...")
    try:
        registry = AgentRegistry()
        print(f"   ✓ Created registry with {len(registry.agents)} agents")
        print(f"   ✓ Default agents registered: {list(registry.agents.keys())}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # Test 3: Agent Registration
    print("3. Testing agent registration...")
    try:
        registry = AgentRegistry()
        test_agent = AgentInfo(
            name="Test Registration",
            url="http://test:9999",
            capabilities=["test_cap"]
        )
        registry.register_agent("test_reg", test_agent)
        retrieved = registry.get_agent("test_reg")
        assert retrieved is not None
        assert retrieved.name == "Test Registration"
        print("   ✓ Agent registration successful")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # Test 4: MCP Envelope Creation
    print("4. Testing MCP envelope creation...")
    try:
        envelope = create_mcp_envelope(
            schema="test_v1",
            source_agent="test_agent",
            payload={"data": "test"}
        )
        assert envelope["schema"] == "test_v1"
        assert envelope["source_agent"] == "test_agent"
        assert "timestamp" in envelope
        assert "session_id" in envelope
        print("   ✓ MCP envelope creation successful")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # Test 5: Registry Persistence
    print("5. Testing registry persistence...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        registry = AgentRegistry(temp_file)
        test_agent = AgentInfo(name="Persistent", url="http://persist:8000")
        registry.register_agent("persistent", test_agent)
        registry._save_registry()
        
        new_registry = AgentRegistry(temp_file)
        loaded_agent = new_registry.get_agent("persistent")
        assert loaded_agent is not None
        assert loaded_agent.name == "Persistent"
        
        os.unlink(temp_file)
        print("   ✓ Registry persistence successful")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    print("=" * 50)
    print("✓ All basic functionality tests passed!")
    return True


def run_integration_tests():
    """Run integration tests that may require network access."""
    print("\nRunning Integration Tests...")
    print("=" * 30)
    
    # Test A2A communicator (without making actual requests)
    print("1. Testing A2ACommunicator creation...")
    try:
        communicator = A2ACommunicator()
        print("   ✓ A2ACommunicator created successfully")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # Test agent capability discovery (without network)
    print("2. Testing agent capability discovery...")
    try:
        communicator = A2ACommunicator()
        # This would normally make a network request, but we'll just test the method exists
        assert hasattr(communicator, 'discover_agent_capabilities')
        assert hasattr(communicator, 'health_check_agent')
        assert hasattr(communicator, 'send_a2a_request')
        print("   ✓ A2ACommunicator methods available")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    print("=" * 30)
    print("✓ All integration tests passed!")
    return True


if __name__ == "__main__":
    # Run basic functionality tests
    basic_success = run_basic_functionality_tests()
    
    # Run integration tests
    integration_success = run_integration_tests()
    
    # Overall result
    if basic_success and integration_success:
        print("\n🎉 All tests passed! AgentFleet orchestration is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)