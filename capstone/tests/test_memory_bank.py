#!/usr/bin/env python3
"""
Quick test script for Memory Bank functionality.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add capstone to path
sys.path.insert(0, os.path.dirname(__file__))

from capstone.memory_bank import MemoryBank, get_memory_bank
from capstone.tools.memory_tools import (
    query_memory_bank,
    store_incident_memory,
    get_memory_bank_stats
)


def test_memory_bank():
    """Test Memory Bank basic functionality."""
    print("Testing Memory Bank Implementation...")
    print("=" * 60)
    
    # Check if API key is set
    if not os.getenv("GOOGLE_API_KEY"):
        print("❌ GOOGLE_API_KEY not set in environment")
        print("Please set GOOGLE_API_KEY to test Memory Bank")
        return False
    
    try:
        # Test 1: Initialize Memory Bank
        print("\n1. Initializing Memory Bank...")
        memory_bank = get_memory_bank()
        print("✓ Memory Bank initialized successfully")
        
        # Test 2: Store incidents
        print("\n2. Storing test incidents...")
        
        incidents = [
            {
                "incident_id": "test_001",
                "summary": "Major flooding in downtown area affecting multiple buildings",
                "severity": "HIGH",
                "location": "Downtown District"
            },
            {
                "incident_id": "test_002",
                "summary": "Power outage in residential neighborhood due to storm",
                "severity": "MEDIUM",
                "location": "North Residential"
            },
            {
                "incident_id": "test_003",
                "summary": "Water main break causing street flooding",
                "severity": "HIGH",
                "location": "Main Street"
            }
        ]
        
        for incident in incidents:
            result = store_incident_memory(**incident)
            if result["success"]:
                print(f"✓ Stored: {incident['incident_id']}")
            else:
                print(f"✗ Failed to store: {incident['incident_id']}")
                return False
        
        # Test 3: Get stats
        print("\n3. Checking Memory Bank stats...")
        stats_result = get_memory_bank_stats()
        if stats_result["success"]:
            stats = stats_result["stats"]
            print(f"✓ Total incidents: {stats['total_incidents']}")
            print(f"✓ Embedding dimension: {stats['embedding_dimension']}")
        else:
            print("✗ Failed to get stats")
            return False
        
        # Test 4: Query similar incidents
        print("\n4. Querying for similar incidents...")
        query = "flooding in city streets"
        result = query_memory_bank(query, top_k=3, min_similarity=0.3)
        
        if result["success"]:
            print(f"✓ Found {result['count']} similar incidents for query: '{query}'")
            for i, incident in enumerate(result["results"], 1):
                print(f"\n  Result {i}:")
                print(f"    ID: {incident['incident_id']}")
                print(f"    Similarity: {incident['similarity_score']:.3f}")
                print(f"    Summary: {incident['summary'][:60]}...")
                print(f"    Severity: {incident['severity']}")
        else:
            print(f"✗ Query failed: {result.get('error')}")
            return False
        
        # Test 5: Query with no results
        print("\n5. Testing query with no similar results...")
        result = query_memory_bank("alien invasion from mars", top_k=3, min_similarity=0.8)
        if result["success"]:
            print(f"✓ Query executed, found {result['count']} results (expected 0)")
        else:
            print(f"✗ Query failed: {result.get('error')}")
            return False
        
        print("\n" + "=" * 60)
        print("✓ All Memory Bank tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_memory_bank()
    sys.exit(0 if success else 1)
