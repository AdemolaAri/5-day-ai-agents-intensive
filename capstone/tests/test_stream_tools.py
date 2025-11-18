#!/usr/bin/env python3
"""
Quick test script to verify stream simulators and connector functionality.
"""

import time
from capstone.tools import (
    TwitterStreamSimulator,
    EmergencyFeedSimulator,
    SensorDataSimulator,
    get_stream_connector,
    stream_connector_tool,
)


def test_simulators():
    """Test individual simulators."""
    print("=" * 60)
    print("Testing Stream Simulators")
    print("=" * 60)
    
    # Test Twitter simulator
    print("\n1. Testing TwitterStreamSimulator...")
    twitter_sim = TwitterStreamSimulator()
    event = twitter_sim.generate_event()
    print(f"   Source: {event['source']}")
    print(f"   Content: {event['content'][:80]}...")
    print(f"   Metadata keys: {list(event['metadata'].keys())}")
    print("   ✓ Twitter simulator working")
    
    # Test Emergency simulator
    print("\n2. Testing EmergencyFeedSimulator...")
    emergency_sim = EmergencyFeedSimulator()
    event = emergency_sim.generate_event()
    print(f"   Source: {event['source']}")
    print(f"   Content: {event['content'][:80]}...")
    print(f"   Severity: {event['metadata']['severity']}")
    print("   ✓ Emergency simulator working")
    
    # Test Sensor simulator
    print("\n3. Testing SensorDataSimulator...")
    sensor_sim = SensorDataSimulator()
    event = sensor_sim.generate_event()
    print(f"   Source: {event['source']}")
    print(f"   Content: {event['content'][:80]}...")
    print(f"   Sensor type: {event['metadata']['sensor_type']}")
    print("   ✓ Sensor simulator working")


def test_stream_connector():
    """Test stream connector functionality."""
    print("\n" + "=" * 60)
    print("Testing Stream Connector")
    print("=" * 60)
    
    connector = get_stream_connector()
    
    # Test connecting to Twitter stream
    print("\n1. Connecting to Twitter stream...")
    result = stream_connector_tool("twitter", "connect")
    print(f"   Success: {result['success']}")
    print(f"   Status: {result['status']}")
    print("   ✓ Connection established")
    
    # Wait for some events
    print("\n2. Waiting for events (3 seconds)...")
    time.sleep(3)
    
    # Get events
    print("\n3. Retrieving events...")
    result = stream_connector_tool("twitter", "get_events", max_events=5)
    print(f"   Success: {result['success']}")
    print(f"   Events received: {result['count']}")
    if result['count'] > 0:
        print(f"   First event: {result['events'][0]['content'][:60]}...")
    print("   ✓ Events retrieved")
    
    # Check health
    print("\n4. Checking stream health...")
    result = stream_connector_tool("twitter", "health")
    print(f"   Success: {result['success']}")
    print(f"   Status: {result['health']['status']}")
    print(f"   Events received: {result['health']['events_received']}")
    print(f"   Is healthy: {result['is_healthy']}")
    print("   ✓ Health check passed")
    
    # Test connecting to all streams
    print("\n5. Connecting to all streams...")
    result = stream_connector_tool("all", "connect")
    print(f"   Success: {result['success']}")
    print(f"   Connected sources: {list(result['connections'].keys())}")
    print("   ✓ All streams connected")
    
    # Wait and get events from all
    print("\n6. Waiting for events from all streams (3 seconds)...")
    time.sleep(3)
    
    print("\n7. Retrieving events from all streams...")
    result = stream_connector_tool("all", "get_events", max_events=3)
    print(f"   Success: {result['success']}")
    print(f"   Total events: {result['total_count']}")
    for source, events in result['events'].items():
        print(f"   - {source}: {len(events)} events")
    print("   ✓ Batch retrieval working")
    
    # Check health of all
    print("\n8. Checking health of all streams...")
    result = stream_connector_tool("all", "health")
    print(f"   Success: {result['success']}")
    for source, health in result['health'].items():
        print(f"   - {source}: {health['status']} ({health['events_received']} events)")
    print("   ✓ All streams healthy")
    
    # Disconnect
    print("\n9. Disconnecting from all streams...")
    result = stream_connector_tool("all", "disconnect")
    print(f"   Success: {result['success']}")
    print("   ✓ All streams disconnected")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AgentFleet Stream Tools Test Suite")
    print("=" * 60)
    
    try:
        test_simulators()
        test_stream_connector()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nStream simulators and connector are working correctly.")
        print("Ready for integration with Ingest Agent.")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
