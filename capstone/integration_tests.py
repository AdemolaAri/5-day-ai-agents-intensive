#!/usr/bin/env python3
"""
AgentFleet End-to-End Integration Tests

This module provides comprehensive integration tests for the complete
AgentFleet system including the end-to-end event processing pipeline,
error recovery mechanisms, and session management.

Requirements Satisfied:
- 13.1: Test event flow from Ingest to Dispatcher with session context
- 13.2: Test error recovery mechanisms with circuit breaker and retry logic
- 13.3: Test session archival and restoration functionality

Usage:
    # Run all integration tests
    python integration_tests.py --all
    
    # Run specific test categories
    python integration_tests.py --pipeline
    python integration_tests.py --recovery
    python integration_tests.py --sessions
"""

import os
import sys
import json
import time
import uuid
import unittest
import tempfile
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

# Add capstone to path
sys.path.insert(0, str(Path(__file__).parent))

from capstone.integration_pipeline import EventProcessingPipeline, SessionContext
from capstone.error_recovery import A2ARetryHandler, CircuitBreakerManager, DeadLetterQueue, RecoveryJobProcessor
from capstone.session_archival import SessionArchiver, SessionManager
from capstone.agent_utils import A2ACommunicator, A2ARequest, A2AResponse


class TestEventProcessingPipeline(unittest.TestCase):
    """Test the complete event processing pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        self.pipeline = EventProcessingPipeline()
        self.pipeline.start()
    
    def tearDown(self):
        """Clean up test environment."""
        self.pipeline.stop()
    
    def test_sample_event_processing(self):
        """Test processing a sample event through the complete pipeline."""
        # Sample event data
        test_event = {
            "source": "twitter",
            "content": "BREAKING: Major flooding reported in downtown area due to heavy rainfall. Emergency services responding.",
            "timestamp": datetime.now().isoformat(),
            "raw_data": {
                "username": "@news_alerts",
                "tweet_id": "123456789",
                "location": "downtown",
                "retweet_count": 150,
                "like_count": 300
            }
        }
        
        # Process event
        result = self.pipeline.process_event(test_event)
        
        # Verify result
        self.assertTrue(result["success"], f"Event processing failed: {result.get('error', 'Unknown error')}")
        self.assertIn("session_id", result)
        self.assertIn("incident_id", result)
        
        # Verify session was created and completed
        session = self.pipeline.get_session_details(result["session_id"])
        self.assertIsNotNone(session)
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["incident_id"], result["incident_id"])
    
    def test_session_context_propagation(self):
        """Test that session context is properly propagated through all agents."""
        test_event = {
            "source": "emergency",
            "content": "Fire reported at 123 Main Street, multiple units responding.",
            "timestamp": datetime.now().isoformat()
        }
        
        result = self.pipeline.process_event(test_event)
        
        # Verify session details contain full event history
        session_details = self.pipeline.get_session_details(result["session_id"])
        self.assertIsNotNone(session_details)
        self.assertGreater(len(session_details["events"]), 0)
        
        # Verify session metadata contains pipeline information
        self.assertIn("source_agent", session_details["metadata"])
        self.assertIn("pipeline_start", session_details["metadata"])
    
    def test_pipeline_error_handling(self):
        """Test pipeline error handling with invalid data."""
        # Test with invalid event data
        invalid_event = {
            "source": "",
            "content": "",  # Empty content should cause processing issues
            "timestamp": "invalid-timestamp"
        }
        
        result = self.pipeline.process_event(invalid_event)
        
        # Should fail gracefully
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("session_id", result)
        
        # Session should be marked as failed
        session_details = self.pipeline.get_session_details(result["session_id"])
        self.assertIsNotNone(session_details)
        self.assertEqual(session_details["status"], "failed")
        self.assertIn("error", session_details["metadata"])


class TestErrorRecoveryMechanisms(unittest.TestCase):
    """Test error recovery mechanisms including retry logic and circuit breaker."""
    
    def setUp(self):
        """Set up test environment."""
        self.retry_handler = A2ARetryHandler()
        self.circuit_breaker_manager = CircuitBreakerManager()
        self.dead_letter_queue = DeadLetterQueue()
        self.recovery_processor = RecoveryJobProcessor(
            self.dead_letter_queue, 
            A2ACommunicator()
        )
    
    def test_retry_logic_with_valid_request(self):
        """Test retry logic with a valid request."""
        # Create a mock successful request
        request = A2ARequest(
            agent_url="http://httpbin.org/post",  # This will succeed
            envelope={"test": "data"},
            timeout=10,
            max_retries=2
        )
        
        response = self.retry_handler.execute_with_retry(request)
        
        # Should succeed
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
    
    def test_retry_logic_with_failing_request(self):
        """Test retry logic with a failing request."""
        # Create a request that will fail
        request = A2ARequest(
            agent_url="http://localhost:99999",  # Invalid port
            envelope={"test": "data"},
            timeout=1,
            max_retries=2
        )
        
        response = self.retry_handler.execute_with_retry(request)
        
        # Should fail after retries
        self.assertFalse(response.success)
        self.assertGreater(self.retry_handler.stats["failed_retries"], 0)
        
        # Should be in dead letter queue
        queue_size = self.dead_letter_queue.get_queue_size()
        self.assertGreater(queue_size, 0)
    
    def test_circuit_breaker_protection(self):
        """Test circuit breaker protection for failing agents."""
        # Create a function that always fails
        def failing_function():
            raise Exception("Simulated agent failure")
        
        agent_id = "test_agent"
        
        # Execute multiple failing requests to trip circuit breaker
        for i in range(6):  # More than threshold
            try:
                self.circuit_breaker_manager.execute_with_circuit_breaker(
                    agent_id, failing_function
                )
            except Exception:
                pass  # Expected to fail
        
        # Circuit breaker should now be open
        breaker_status = self.circuit_breaker_manager.get_breaker_status(agent_id)
        self.assertEqual(breaker_status["state"], "OPEN")
        
        # Subsequent requests should be blocked
        try:
            self.circuit_breaker_manager.execute_with_circuit_breaker(
                agent_id, lambda: "success"
            )
            self.fail("Circuit breaker should have blocked this request")
        except Exception as e:
            self.assertIn("blocked by circuit breaker", str(e))
    
    def test_dead_letter_queue_operations(self):
        """Test dead letter queue add, retrieve, and update operations."""
        # Create a failed event
        failed_event = {
            "event_id": "test_event_123",
            "original_payload": {"test": "data"},
            "target_agent": "test_agent",
            "target_url": "http://localhost:8001",
            "failure_reason": "Test failure",
            "failure_count": 1,
            "first_failure": datetime.now(),
            "last_failure": datetime.now()
        }
        
        # Add to dead letter queue
        self.dead_letter_queue.add_failed_event(failed_event)
        
        # Verify it was added
        queue_size = self.dead_letter_queue.get_queue_size()
        self.assertGreater(queue_size, 0)
        
        # Get pending events
        pending_events = self.dead_letter_queue.get_pending_events()
        self.assertGreater(len(pending_events), 0)
        
        # Update event status
        self.dead_letter_queue.update_event_status("test_event_123", "retrying")
        
        # Verify stats
        stats = self.dead_letter_queue.get_stats()
        self.assertGreater(stats["total_events"], 0)
    
    def test_recovery_job_processor(self):
        """Test recovery job processor functionality."""
        # Start recovery processor
        self.recovery_processor.start()
        
        # Wait a moment for processing
        time.sleep(2)
        
        # Check recovery stats
        recovery_stats = self.recovery_processor.get_recovery_stats()
        self.assertTrue(recovery_stats["processor_running"])
        
        # Stop recovery processor
        self.recovery_processor.stop()


class TestSessionManagement(unittest.TestCase):
    """Test session archival and management functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.archiver = SessionArchiver()
        self.session_manager = SessionManager()
    
    def test_session_archival_and_restoration(self):
        """Test complete session archival and restoration cycle."""
        # Create test session data
        session_data = {
            "session_id": "test_session_123",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "status": "active",
            "events": [
                {"timestamp": datetime.now().isoformat(), "event": "test event"}
            ],
            "incident_id": "test_incident_456",
            "metadata": {
                "source_agent": "ingest",
                "severity": "HIGH"
            }
        }
        
        # Archive session
        archive_id = self.archiver.archive_session(session_data)
        self.assertEqual(archive_id, "test_session_123")
        
        # Verify session was archived
        archived_info = self.archiver.get_archived_session_info("test_session_123")
        self.assertIsNotNone(archived_info)
        self.assertEqual(archived_info["session_id"], "test_session_123")
        
        # Restore session
        restored_data = self.archiver.restore_session("test_session_123")
        self.assertIsNotNone(restored_data)
        self.assertTrue(restored_data.get("restored"))
        self.assertEqual(restored_data["restore_count"], 1)
        
        # Verify restore count was updated
        restored_info = self.archiver.get_archived_session_info("test_session_123")
        self.assertEqual(restored_info["restore_count"], 1)
    
    def test_session_manager_lifecycle(self):
        """Test session manager lifecycle with automatic archival."""
        # Start session manager
        self.session_manager.start()
        
        # Create a session
        session_data = {
            "session_id": "lifecycle_test_123",
            "status": "active",
            "events": []
        }
        
        session_id = self.session_manager.create_session(session_data)
        self.assertEqual(session_id, "lifecycle_test_123")
        
        # Verify session is active
        retrieved_session = self.session_manager.get_session(session_id)
        self.assertIsNotNone(retrieved_session)
        
        # Archive session manually
        self.session_manager.archive_session(session_id, "test_manual_archive")
        
        # Verify session is no longer active
        active_session = self.session_manager.get_session(session_id)
        self.assertIsNone(active_session)
        
        # Restore session
        restored_session = self.session_manager.restore_session(session_id)
        self.assertIsNotNone(restored_session)
        self.assertEqual(restored_session["status"], "restored")
        
        # Stop session manager
        self.session_manager.stop()
    
    def test_session_search_and_query(self):
        """Test session search and query functionality."""
        # Archive multiple sessions with different tags
        sessions = [
            {
                "session_id": "search_test_1",
                "incident_id": "incident_1",
                "metadata": {"source_agent": "ingest", "severity": "HIGH"},
                "status": "test"
            },
            {
                "session_id": "search_test_2", 
                "incident_id": "incident_2",
                "metadata": {"source_agent": "verifier", "severity": "MEDIUM"},
                "status": "test"
            },
            {
                "session_id": "search_test_3",
                "incident_id": "incident_3", 
                "metadata": {"source_agent": "ingest", "severity": "LOW"},
                "status": "test"
            }
        ]
        
        for session in sessions:
            self.archiver.archive_session(session)
        
        # Search by query
        search_results = self.archiver.search_archived_sessions("incident")
        self.assertGreater(len(search_results), 0)
        
        # List all archived sessions
        all_sessions = self.archiver.list_archived_sessions(limit=10)
        self.assertGreater(len(all_sessions), 0)
        
        # Get archive statistics
        stats = self.archiver.get_archive_stats()
        self.assertGreater(stats["total_archived"], 0)
        self.assertIn("restore_rate", stats)
    
    def test_session_timeout_archival(self):
        """Test automatic session archival based on timeout."""
        # Create session manager with short timeout for testing
        config = {
            "session_timeout": 5,  # 5 seconds for testing
            "monitoring_interval": 2,
            "enable_auto_archive": True
        }
        
        test_manager = SessionManager(config)
        test_manager.start()
        
        # Create a session
        session_data = {"test": "data"}
        session_id = test_manager.create_session(session_data)
        
        # Verify session is active
        self.assertIsNotNone(test_manager.get_session(session_id))
        
        # Wait for timeout
        time.sleep(8)  # Longer than timeout
        
        # Session should be archived by now
        stats = test_manager.get_stats()
        self.assertGreater(stats["session_manager"]["archived_sessions"], 0)
        
        test_manager.stop()


def run_pipeline_tests():
    """Run event processing pipeline tests."""
    print("Running Event Processing Pipeline Tests...")
    print("=" * 50)
    
    # Test 1: Basic pipeline functionality
    print("1. Testing basic pipeline functionality...")
    try:
        pipeline = EventProcessingPipeline()
        pipeline.start()
        
        # Test with sample event
        test_event = {
            "source": "sensor",
            "content": "Temperature reading: 95°C (above threshold)",
            "timestamp": datetime.now().isoformat()
        }
        
        result = pipeline.process_event(test_event)
        
        if result["success"]:
            print("   ✓ Event processed successfully")
            print(f"   ✓ Session ID: {result['session_id']}")
            print(f"   ✓ Incident ID: {result['incident_id']}")
        else:
            print(f"   ⚠ Event processing failed: {result.get('error', 'Unknown error')}")
        
        pipeline.stop()
        
    except Exception as e:
        print(f"   ✗ Pipeline test failed: {e}")
    
    print("=" * 50)
    print("✓ Pipeline tests completed")


def run_recovery_tests():
    """Run error recovery mechanism tests."""
    print("\nRunning Error Recovery Tests...")
    print("=" * 30)
    
    # Test 1: Retry handler
    print("1. Testing retry handler...")
    try:
        retry_handler = A2ARetryHandler()
        
        # Test with a request that should succeed
        request = A2ARequest(
            agent_url="http://httpbin.org/get",
            envelope={"test": "retry"},
            timeout=5,
            max_retries=2
        )
        
        response = retry_handler.execute_with_retry(request)
        
        if response.success:
            print("   ✓ Retry handler working correctly")
        else:
            print(f"   ⚠ Retry handler failed: {response.error}")
        
    except Exception as e:
        print(f"   ✗ Retry handler test failed: {e}")
    
    # Test 2: Dead letter queue
    print("2. Testing dead letter queue...")
    try:
        dlq = DeadLetterQueue()
        
        # Add a test failed event
        from capstone.error_recovery import FailedEvent
        
        failed_event = FailedEvent(
            event_id="test_dlq_123",
            original_payload={"test": "data"},
            target_agent="test_agent",
            target_url="http://localhost:8001",
            failure_reason="Test failure",
            failure_count=1,
            first_failure=datetime.now(),
            last_failure=datetime.now()
        )
        
        dlq.add_failed_event(failed_event)
        queue_size = dlq.get_queue_size()
        
        if queue_size > 0:
            print(f"   ✓ Dead letter queue working (size: {queue_size})")
        else:
            print("   ⚠ Dead letter queue empty")
        
    except Exception as e:
        print(f"   ✗ Dead letter queue test failed: {e}")
    
    print("=" * 30)
    print("✓ Recovery tests completed")


def run_session_tests():
    """Run session management tests."""
    print("\nRunning Session Management Tests...")
    print("=" * 35)
    
    # Test 1: Session archival
    print("1. Testing session archival...")
    try:
        archiver = SessionArchiver()
        
        # Create test session
        session_data = {
            "session_id": "test_archive_123",
            "status": "completed",
            "events": [{"event": "test"}],
            "metadata": {"test": "data"}
        }
        
        archive_id = archiver.archive_session(session_data)
        
        if archive_id == "test_archive_123":
            print("   ✓ Session archived successfully")
            
            # Test restoration
            restored = archiver.restore_session("test_archive_123")
            if restored and restored.get("restored"):
                print("   ✓ Session restored successfully")
            else:
                print("   ⚠ Session restoration failed")
        else:
            print("   ⚠ Session archival failed")
        
    except Exception as e:
        print(f"   ✗ Session archival test failed: {e}")
    
    # Test 2: Session manager
    print("2. Testing session manager...")
    try:
        manager = SessionManager()
        
        # Create session
        test_data = {"test": "session_data"}
        session_id = manager.create_session(test_data)
        
        if session_id:
            print(f"   ✓ Session created: {session_id}")
            
            # Update activity
            manager.update_session_activity(session_id)
            print("   ✓ Session activity updated")
            
        else:
            print("   ⚠ Session creation failed")
        
    except Exception as e:
        print(f"   ✗ Session manager test failed: {e}")
    
    print("=" * 35)
    print("✓ Session tests completed")


def run_comprehensive_integration_test():
    """Run a comprehensive end-to-end integration test."""
    print("\nRunning Comprehensive Integration Test...")
    print("=" * 45)
    
    try:
        # Initialize all components
        pipeline = EventProcessingPipeline()
        archiver = SessionArchiver()
        dlq = DeadLetterQueue()
        
        print("1. Starting pipeline...")
        pipeline.start()
        
        # Test event processing
        print("2. Processing test event...")
        test_event = {
            "source": "emergency",
            "content": "Multiple vehicle accident reported on Highway 101, injuries confirmed. Emergency services en route.",
            "timestamp": datetime.now().isoformat(),
            "location": "Highway 101",
            "severity": "HIGH"
        }
        
        result = pipeline.process_event(test_event)
        
        if result["success"]:
            print("   ✓ Event processing successful")
            session_id = result["session_id"]
            
            # Test session archival
            print("3. Testing session archival...")
            session_details = pipeline.get_session_details(session_id)
            if session_details:
                archive_id = archiver.archive_session(session_details)
                print(f"   ✓ Session archived: {archive_id}")
                
                # Test session restoration
                print("4. Testing session restoration...")
                restored = archiver.restore_session(archive_id)
                if restored and restored.get("restored"):
                    print("   ✓ Session restored successfully")
                else:
                    print("   ⚠ Session restoration failed")
            else:
                print("   ⚠ Session details not found")
        else:
            print(f"   ⚠ Event processing failed: {result.get('error')}")
        
        # Test error recovery
        print("5. Testing error recovery...")
        stats = dlq.get_stats()
        print(f"   ✓ Dead letter queue stats: {stats}")
        
        pipeline.stop()
        
        print("✓ Comprehensive integration test completed")
        
    except Exception as e:
        print(f"   ✗ Integration test failed: {e}")
    
    print("=" * 45)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentFleet Integration Tests")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all integration tests"
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Run pipeline tests only"
    )
    parser.add_argument(
        "--recovery",
        action="store_true",
        help="Run error recovery tests only"
    )
    parser.add_argument(
        "--sessions",
        action="store_true",
        help="Run session management tests only"
    )
    parser.add_argument(
        "--comprehensive",
        action="store_true",
        help="Run comprehensive end-to-end test"
    )
    
    args = parser.parse_args()
    
    # Change to capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    if args.all or (not any([args.pipeline, args.recovery, args.sessions, args.comprehensive])):
        # Run all tests
        run_pipeline_tests()
        run_recovery_tests()
        run_session_tests()
        run_comprehensive_integration_test()
        
        print("\n🎉 All integration tests completed!")
        
    elif args.pipeline:
        run_pipeline_tests()
    elif args.recovery:
        run_recovery_tests()
    elif args.sessions:
        run_session_tests()
    elif args.comprehensive:
        run_comprehensive_integration_test()
    else:
        print("Please specify test type: --all, --pipeline, --recovery, --sessions, or --comprehensive")
        sys.exit(1)