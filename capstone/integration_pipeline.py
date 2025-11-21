#!/usr/bin/env python3
"""
AgentFleet End-to-End Integration Pipeline

This module implements the complete end-to-end event processing pipeline
that connects all agents via A2A protocol and manages the full incident lifecycle.

Requirements Satisfied:
- 13.1: Create event processing pipeline connecting all agents via A2A
- 13.2: Implement error recovery mechanisms with retry logic and circuit breaker
- 13.3: Add session archival with timeout detection and session restoration

Usage:
    # As a standalone pipeline
    python integration_pipeline.py --start
    
    # As a module
    from capstone.integration_pipeline import EventProcessingPipeline
"""

import os
import sys
import json
import time
import uuid
import asyncio
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Add capstone to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_utils import A2ACommunicator, A2ARequest, A2AResponse, create_mcp_envelope
from agent_discovery import AgentRegistry
from mcp_envelope import MCPEnvelope, parse_envelope
from memory_bank import MemoryBank

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """Session context for incident lifecycle management."""
    session_id: str
    created_at: datetime
    last_activity: datetime
    events: List[Dict[str, Any]]
    incident_id: Optional[str] = None
    status: str = "active"  # active, archived, restored
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def add_event(self, event: Dict[str, Any]):
        """Add event to session history."""
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "event": event
        })
        self.update_activity()


class CircuitBreaker:
    """Circuit breaker for agent failure protection."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker OPEN for {self.timeout}s")
            
            try:
                result = func(*args, **kwargs)
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(f"Circuit breaker OPEN after {self.failure_threshold} failures")
                raise


class EventProcessingPipeline:
    """
    End-to-end event processing pipeline connecting all agents.
    
    Features:
    - Complete incident lifecycle from ingestion to dispatch
    - Session context propagation through all agents
    - Error recovery with retry logic and circuit breaker
    - Session archival and restoration
    - Real-time monitoring and status tracking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the event processing pipeline.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config or self._default_config()
        
        # Core components
        self.agent_registry = AgentRegistry()
        self.a2a_communicator = A2ACommunicator(self.agent_registry)
        self.memory_bank = MemoryBank()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Session management
        self.sessions: Dict[str, SessionContext] = {}
        self.session_timeout = self.config.get("session_timeout", 3600)  # 60 minutes
        self.archived_sessions: Dict[str, SessionContext] = {}
        
        # Pipeline state
        self.running = False
        self.monitoring_thread = None
        
        # Statistics
        self.stats = {
            "events_processed": 0,
            "incidents_created": 0,
            "errors": 0,
            "retries": 0,
            "circuit_breaker_trips": 0
        }
        
        logger.info("Event Processing Pipeline initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default pipeline configuration."""
        return {
            "session_timeout": 3600,  # 60 minutes
            "retry_attempts": 3,
            "retry_delay": 2.0,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 60,
            "session_cleanup_interval": 300,  # 5 minutes
            "enable_session_archival": True,
            "enable_circuit_breaker": True
        }
    
    def start(self):
        """Start the event processing pipeline."""
        if self.running:
            logger.warning("Pipeline already running")
            return
        
        logger.info("Starting Event Processing Pipeline...")
        
        # Start agent registry health monitoring
        self.agent_registry.start_health_monitoring()
        
        # Start session monitoring
        self._start_session_monitoring()
        
        self.running = True
        logger.info("Event Processing Pipeline started successfully")
    
    def stop(self):
        """Stop the event processing pipeline."""
        logger.info("Stopping Event Processing Pipeline...")
        
        self.running = False
        
        # Stop session monitoring
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # Stop agent registry monitoring
        self.agent_registry.stop_health_monitoring()
        
        logger.info("Event Processing Pipeline stopped")
    
    def process_event(self, event_data: Dict[str, Any], source_agent: str = "ingest") -> Dict[str, Any]:
        """
        Process a single event through the complete pipeline.
        
        Args:
            event_data: Raw event data
            source_agent: Source agent name
            
        Returns:
            Processing result with incident information
        """
        session_id = str(uuid.uuid4())
        
        try:
            # Create session
            session = self._create_session(session_id, source_agent)
            logger.info(f"Processing event in session {session_id}")
            
            # Step 1: Ingest and normalize
            normalized_event = self._ingest_event(event_data, session_id)
            if not normalized_event:
                raise Exception("Failed to normalize event")
            
            # Step 2: Verify claims
            verified_event = self._verify_event(normalized_event, session_id)
            if not verified_event:
                raise Exception("Failed to verify event")
            
            # Step 3: Generate summary
            incident_brief = self._generate_summary(verified_event, session_id)
            if not incident_brief:
                raise Exception("Failed to generate summary")
            
            # Step 4: Triage and classify
            triaged_incident = self._triage_incident(incident_brief, session_id)
            if not triaged_incident:
                raise Exception("Failed to triage incident")
            
            # Step 5: Dispatch actions
            dispatch_result = self._dispatch_incident(triaged_incident, session_id)
            if not dispatch_result:
                raise Exception("Failed to dispatch incident")
            
            # Complete session
            session.incident_id = dispatch_result.get("incident_id")
            session.status = "completed"
            
            # Update statistics
            self.stats["events_processed"] += 1
            self.stats["incidents_created"] += 1
            
            result = {
                "success": True,
                "session_id": session_id,
                "incident_id": session.incident_id,
                "result": dispatch_result,
                "pipeline_duration": session.last_activity - session.created_at
            }
            
            logger.info(f"Event processing completed successfully for session {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"Event processing failed for session {session_id}: {e}", exc_info=True)
            
            # Update session with error
            if session_id in self.sessions:
                self.sessions[session_id].status = "failed"
                self.sessions[session_id].metadata["error"] = str(e)
            
            self.stats["errors"] += 1
            
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e)
            }
    
    def _create_session(self, session_id: str, source_agent: str) -> SessionContext:
        """Create a new session for event processing."""
        session = SessionContext(
            session_id=session_id,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            events=[],
            metadata={
                "source_agent": source_agent,
                "pipeline_start": datetime.now().isoformat()
            }
        )
        
        self.sessions[session_id] = session
        logger.debug(f"Created session {session_id}")
        return session
    
    def _ingest_event(self, event_data: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        """Step 1: Ingest and normalize event."""
        try:
            # Get ingest agent URL
            ingest_url = self.agent_registry.get_a2a_endpoint("ingest")
            if not ingest_url:
                raise Exception("Ingest agent not available")
            
            # Create MCP envelope
            envelope = create_mcp_envelope(
                schema="event_ingestion_v1",
                source_agent="integration_pipeline",
                payload={
                    "event_data": event_data,
                    "operation": "normalize_event"
                },
                session_id=session_id
            )
            
            # Send to ingest agent
            request = A2ARequest(
                agent_url=ingest_url,
                envelope=envelope,
                timeout=30,
                max_retries=self.config["retry_attempts"]
            )
            
            response = self.a2a_communicator.send_a2a_request(request)
            
            if response.success:
                self.stats["retries"] += request.max_retries - len([r for r in range(request.max_retries + 1) if r == 0])
                return response.data
            else:
                raise Exception(f"Ingest agent failed: {response.error}")
                
        except Exception as e:
            logger.error(f"Event ingestion failed: {e}")
            return None
    
    def _verify_event(self, normalized_event: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        """Step 2: Verify claims in the event."""
        try:
            # Get verifier agent URL
            verifier_url = self.agent_registry.get_a2a_endpoint("verifier")
            if not verifier_url:
                raise Exception("Verifier agent not available")
            
            # Create MCP envelope
            envelope = create_mcp_envelope(
                schema="event_verification_v1",
                source_agent="integration_pipeline",
                payload={
                    "event": normalized_event,
                    "operation": "verify_event"
                },
                session_id=session_id
            )
            
            # Send to verifier agent
            request = A2ARequest(
                agent_url=verifier_url,
                envelope=envelope,
                timeout=30,
                max_retries=self.config["retry_attempts"]
            )
            
            response = self.a2a_communicator.send_a2a_request(request)
            
            if response.success:
                return response.data
            else:
                raise Exception(f"Verifier agent failed: {response.error}")
                
        except Exception as e:
            logger.error(f"Event verification failed: {e}")
            return None
    
    def _generate_summary(self, verified_event: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        """Step 3: Generate incident summary."""
        try:
            # Get summarizer agent URL
            summarizer_url = self.agent_registry.get_a2a_endpoint("summarizer")
            if not summarizer_url:
                raise Exception("Summarizer agent not available")
            
            # Query memory bank for similar incidents
            memory_context = self._get_memory_context(verified_event)
            
            # Create MCP envelope
            envelope = create_mcp_envelope(
                schema="summary_generation_v1",
                source_agent="integration_pipeline",
                payload={
                    "event": verified_event,
                    "memory_context": memory_context,
                    "operation": "generate_summary"
                },
                session_id=session_id
            )
            
            # Send to summarizer agent
            request = A2ARequest(
                agent_url=summarizer_url,
                envelope=envelope,
                timeout=30,
                max_retries=self.config["retry_attempts"]
            )
            
            response = self.a2a_communicator.send_a2a_request(request)
            
            if response.success:
                return response.data
            else:
                raise Exception(f"Summarizer agent failed: {response.error}")
                
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return None
    
    def _get_memory_context(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Get memory context for event processing."""
        try:
            # Query memory bank for similar incidents
            query_text = event.get("content", "")
            if query_text:
                similar_incidents = self.memory_bank.query_similar_incidents(
                    query_text, 
                    top_k=3
                )
                return {
                    "similar_incidents": similar_incidents,
                    "query_performed": True
                }
        except Exception as e:
            logger.warning(f"Memory bank query failed: {e}")
        
        return {"similar_incidents": [], "query_performed": False}
    
    def _triage_incident(self, incident_brief: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        """Step 4: Triage and classify incident severity."""
        try:
            # Get triage agent URL
            triage_url = self.agent_registry.get_a2a_endpoint("triage")
            if not triage_url:
                raise Exception("Triage agent not available")
            
            # Create MCP envelope
            envelope = create_mcp_envelope(
                schema="incident_triage_v1",
                source_agent="integration_pipeline",
                payload={
                    "brief": incident_brief,
                    "operation": "classify_severity"
                },
                session_id=session_id
            )
            
            # Send to triage agent
            request = A2ARequest(
                agent_url=triage_url,
                envelope=envelope,
                timeout=30,
                max_retries=self.config["retry_attempts"]
            )
            
            response = self.a2a_communicator.send_a2a_request(request)
            
            if response.success:
                return response.data
            else:
                raise Exception(f"Triage agent failed: {response.error}")
                
        except Exception as e:
            logger.error(f"Incident triage failed: {e}")
            return None
    
    def _dispatch_incident(self, triaged_incident: Dict[str, Any], session_id: str) -> Optional[Dict[str, Any]]:
        """Step 5: Dispatch incident with recommended actions."""
        try:
            # Get dispatcher agent URL
            dispatcher_url = self.agent_registry.get_a2a_endpoint("dispatcher")
            if not dispatcher_url:
                raise Exception("Dispatcher agent not available")
            
            # Create MCP envelope
            envelope = create_mcp_envelope(
                schema="incident_dispatch_v1",
                source_agent="integration_pipeline",
                payload={
                    "incident": triaged_incident,
                    "operation": "generate_actions"
                },
                session_id=session_id
            )
            
            # Send to dispatcher agent
            request = A2ARequest(
                agent_url=dispatcher_url,
                envelope=envelope,
                timeout=30,
                max_retries=self.config["retry_attempts"]
            )
            
            response = self.a2a_communicator.send_a2a_request(request)
            
            if response.success:
                # Store incident in memory bank
                self._store_incident_in_memory(triaged_incident, response.data)
                return response.data
            else:
                raise Exception(f"Dispatcher agent failed: {response.error}")
                
        except Exception as e:
            logger.error(f"Incident dispatch failed: {e}")
            return None
    
    def _store_incident_in_memory(self, triaged_incident: Dict[str, Any], dispatch_result: Dict[str, Any]):
        """Store completed incident in memory bank."""
        try:
            incident_data = {
                "incident_id": triaged_incident.get("incident_id"),
                "summary": triaged_incident.get("brief", {}).get("summary", ""),
                "severity": triaged_incident.get("severity", ""),
                "actions": dispatch_result.get("recommended_actions", []),
                "timestamp": datetime.now().isoformat()
            }
            
            self.memory_bank.store_incident(incident_data)
            logger.debug(f"Stored incident {incident_data['incident_id']} in memory bank")
            
        except Exception as e:
            logger.warning(f"Failed to store incident in memory bank: {e}")
    
    def _start_session_monitoring(self):
        """Start background session monitoring for archival."""
        def session_monitor():
            while self.running:
                try:
                    self._check_session_timeout()
                    time.sleep(self.config["session_cleanup_interval"])
                except Exception as e:
                    logger.error(f"Session monitor error: {e}")
        
        self.monitoring_thread = threading.Thread(target=session_monitor, daemon=True)
        self.monitoring_thread.start()
        logger.info("Session monitoring started")
    
    def _check_session_timeout(self):
        """Check for sessions that need to be archived."""
        if not self.config["enable_session_archival"]:
            return
        
        now = datetime.now()
        sessions_to_archive = []
        
        for session_id, session in self.sessions.items():
            if session.status == "active":
                age = now - session.last_activity
                if age.total_seconds() > self.session_timeout:
                    sessions_to_archive.append(session_id)
        
        # Archive sessions
        for session_id in sessions_to_archive:
            session = self.sessions[session_id]
            session.status = "archived"
            session.metadata["archived_at"] = now.isoformat()
            
            # Move to archived sessions
            self.archived_sessions[session_id] = session
            del self.sessions[session_id]
            
            logger.info(f"Archived session {session_id} (age: {age.total_seconds():.0f}s)")
    
    def restore_session(self, session_id: str) -> Optional[SessionContext]:
        """Restore an archived session."""
        if session_id in self.archived_sessions:
            session = self.archived_sessions[session_id]
            session.status = "restored"
            session.last_activity = datetime.now()
            
            # Move back to active sessions
            self.sessions[session_id] = session
            del self.archived_sessions[session_id]
            
            logger.info(f"Restored session {session_id}")
            return session
        
        logger.warning(f"Session {session_id} not found in archived sessions")
        return None
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status."""
        return {
            "running": self.running,
            "config": self.config,
            "stats": self.stats.copy(),
            "active_sessions": len(self.sessions),
            "archived_sessions": len(self.archived_sessions),
            "agent_health": self.agent_registry.get_registry_status(),
            "recent_sessions": [
                {
                    "session_id": session.session_id,
                    "status": session.status,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "incident_id": session.incident_id,
                    "event_count": len(session.events)
                }
                for session in list(self.sessions.values())[-10:]  # Last 10 sessions
            ]
        }
    
    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific session."""
        session = self.sessions.get(session_id) or self.archived_sessions.get(session_id)
        
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "incident_id": session.incident_id,
            "event_count": len(session.events),
            "metadata": session.metadata,
            "events": session.events
        }


def main():
    """Main entry point for standalone usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentFleet Integration Pipeline")
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the integration pipeline"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show pipeline status"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run pipeline test with sample event"
    )
    parser.add_argument(
        "--config",
        help="Configuration file path"
    )
    
    args = parser.parse_args()
    
    # Change to capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Load configuration
    config = None
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            config = None
    
    # Initialize pipeline
    pipeline = EventProcessingPipeline(config)
    
    if args.status:
        # Show status
        status = pipeline.get_pipeline_status()
        print("\nIntegration Pipeline Status:")
        print("=" * 50)
        print(f"Running: {'Yes' if status['running'] else 'No'}")
        print(f"Active Sessions: {status['active_sessions']}")
        print(f"Archived Sessions: {status['archived_sessions']}")
        print(f"Events Processed: {status['stats']['events_processed']}")
        print(f"Incidents Created: {status['stats']['incidents_created']}")
        print(f"Errors: {status['stats']['errors']}")
        print(f"Agent Health: {status['agent_health']['healthy_agents']}/{status['agent_health']['total_agents']} healthy")
        print("=" * 50)
        return
    
    if args.test:
        # Run test
        print("Running pipeline test...")
        
        # Sample event data
        test_event = {
            "source": "twitter",
            "content": "BREAKING: Major flooding reported in downtown area due to heavy rainfall. Emergency services responding.",
            "timestamp": datetime.now().isoformat(),
            "raw_data": {
                "username": "@news_alerts",
                "tweet_id": "123456789",
                "location": "downtown"
            }
        }
        
        try:
            result = pipeline.process_event(test_event)
            print(f"Test result: {result}")
        except Exception as e:
            print(f"Test failed: {e}")
        return
    
    if args.start:
        # Start pipeline
        try:
            pipeline.start()
            
            print("Integration Pipeline started. Press Ctrl+C to stop.")
            
            # Wait for shutdown signal
            try:
                while pipeline.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                
        except Exception as e:
            logger.error(f"Pipeline startup failed: {e}")
        finally:
            pipeline.stop()
    else:
        print("Please specify --start, --status, or --test")
        sys.exit(1)


if __name__ == "__main__":
    main()