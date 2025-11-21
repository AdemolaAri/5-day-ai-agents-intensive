#!/usr/bin/env python3
"""
AgentFleet Main Integration Orchestrator

This script serves as the main entry point for the complete AgentFleet
end-to-end integration. It coordinates all components including the
event processing pipeline, error recovery mechanisms, session management,
and comprehensive monitoring.

Requirements Satisfied:
- 13.1: Complete end-to-end event processing pipeline coordination
- 13.2: Integrated error recovery with circuit breaker and retry logic
- 13.3: Full session lifecycle management with archival and restoration
- All Task 13 sub-requirements comprehensively implemented

Usage:
    # Start complete integration
    python main_integration.py --start
    
    # Monitor integration status
    python main_integration.py --status
    
    # Run integration tests
    python main_integration.py --test
    
    # Emergency shutdown
    python main_integration.py --stop
"""

import os
import sys
import json
import time
import uuid
import signal
import logging
import argparse
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Add capstone to path
sys.path.insert(0, str(Path(__file__).parent))

from integration_pipeline import EventProcessingPipeline
from error_recovery import A2ARetryHandler, CircuitBreakerManager, DeadLetterQueue, RecoveryJobProcessor
from session_archival import SessionArchiver, SessionManager
from agent_discovery import AgentRegistry
from start_agents import AgentOrchestrator
from agent_utils import create_mcp_envelope

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentFleetIntegration:
    """
    Complete AgentFleet integration orchestrator.
    
    Coordinates all components for production-ready operation:
    - Event processing pipeline
    - Error recovery mechanisms
    - Session management and archival
    - Agent discovery and health monitoring
    - Comprehensive statistics and monitoring
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the complete integration.
        
        Args:
            config_file: Path to configuration file
        """
        self.config = self._load_config(config_file)
        
        # Core integration components
        self.pipeline = None
        self.error_recovery = None
        self.session_mgmt = None
        self.agent_registry = None
        self.agent_orchestrator = None
        
        # Integration state
        self.running = False
        self.startup_time = None
        self.shutdown_event = threading.Event()
        
        # Comprehensive monitoring
        self.integration_stats = {
            "startup_time": None,
            "uptime": 0,
            "total_events_processed": 0,
            "total_incidents_created": 0,
            "total_errors": 0,
            "recovery_attempts": 0,
            "sessions_archived": 0,
            "sessions_restored": 0,
            "agent_health_score": 0.0,
            "pipeline_health_score": 0.0
        }
        
        # Background monitoring
        self.monitoring_thread = None
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("AgentFleet Integration initialized")
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load integration configuration."""
        default_config = {
            "pipeline": {
                "session_timeout": 3600,
                "retry_attempts": 3,
                "enable_session_archival": True
            },
            "error_recovery": {
                "max_retries": 3,
                "circuit_breaker_threshold": 5,
                "enable_dead_letter_queue": True,
                "recovery_interval": 300
            },
            "session_management": {
                "archive_timeout": 3600,
                "cleanup_interval": 86400,
                "max_archive_age": 2592000
            },
            "monitoring": {
                "status_interval": 60,
                "health_check_interval": 30,
                "enable_detailed_monitoring": True
            },
            "startup": {
                "wait_for_agents": True,
                "startup_timeout": 300,
                "health_check_retries": 5
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                
                # Deep merge configurations
                self._deep_update(default_config, user_config)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file {config_file}: {e}")
                logger.info("Using default configuration")
        
        return default_config
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict):
        """Deep update a nested dictionary."""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def start(self) -> bool:
        """
        Start the complete AgentFleet integration.
        
        Returns:
            True if startup successful, False otherwise
        """
        if self.running:
            logger.warning("Integration already running")
            return True
        
        logger.info("Starting AgentFleet Integration...")
        self.startup_time = datetime.now()
        self.integration_stats["startup_time"] = self.startup_time.isoformat()
        
        try:
            # Step 1: Start agent orchestrator
            logger.info("1. Starting agent orchestrator...")
            if not self._start_agent_orchestrator():
                logger.error("Failed to start agent orchestrator")
                return False
            
            # Step 2: Start pipeline
            logger.info("2. Starting event processing pipeline...")
            if not self._start_pipeline():
                logger.error("Failed to start event processing pipeline")
                return False
            
            # Step 3: Start error recovery
            logger.info("3. Starting error recovery systems...")
            if not self._start_error_recovery():
                logger.error("Failed to start error recovery systems")
                return False
            
            # Step 4: Start session management
            logger.info("4. Starting session management...")
            if not self._start_session_management():
                logger.error("Failed to start session management")
                return False
            
            # Step 5: Start monitoring
            logger.info("5. Starting integration monitoring...")
            self._start_monitoring()
            
            # Mark as running
            self.running = True
            
            # Update startup stats
            startup_duration = (datetime.now() - self.startup_time).total_seconds()
            logger.info(f"AgentFleet Integration started successfully in {startup_duration:.1f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Integration startup failed: {e}", exc_info=True)
            self._cleanup_on_error()
            return False
    
    def stop(self):
        """Stop the complete integration."""
        if not self.running:
            logger.warning("Integration not running")
            return
        
        logger.info("Stopping AgentFleet Integration...")
        
        self.running = False
        self.shutdown_event.set()
        
        # Stop components in reverse order
        self._stop_monitoring()
        self._stop_session_management()
        self._stop_error_recovery()
        self._stop_pipeline()
        self._stop_agent_orchestrator()
        
        # Update stats
        if self.startup_time:
            self.integration_stats["uptime"] = (
                datetime.now() - self.startup_time
            ).total_seconds()
        
        logger.info("AgentFleet Integration stopped")
    
    def _start_agent_orchestrator(self) -> bool:
        """Start agent orchestrator."""
        try:
            self.agent_orchestrator = AgentOrchestrator()
            
            # Start all agents
            success = self.agent_orchestrator.start_all_agents()
            if not success:
                return False
            
            # Wait for agents to be healthy
            if self.config["startup"]["wait_for_agents"]:
                agent_urls = [
                    "http://localhost:8001",
                    "http://localhost:8002", 
                    "http://localhost:8003",
                    "http://localhost:8004",
                    "http://localhost:8005"
                ]
                
                timeout = self.config["startup"]["startup_timeout"]
                if not self._wait_for_agents_healthy(agent_urls, timeout):
                    logger.error("Timeout waiting for agents to become healthy")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Agent orchestrator startup failed: {e}")
            return False
    
    def _start_pipeline(self) -> bool:
        """Start event processing pipeline."""
        try:
            self.pipeline = EventProcessingPipeline(self.config["pipeline"])
            self.pipeline.start()
            return True
        except Exception as e:
            logger.error(f"Pipeline startup failed: {e}")
            return False
    
    def _start_error_recovery(self) -> bool:
        """Start error recovery systems."""
        try:
            # Initialize components
            self.error_recovery = {
                "retry_handler": A2ARetryHandler(self.config["error_recovery"]),
                "circuit_breaker_manager": CircuitBreakerManager(self.config["error_recovery"]),
                "dead_letter_queue": DeadLetterQueue(),
                "recovery_processor": RecoveryJobProcessor(
                    DeadLetterQueue(),
                    self.pipeline.a2a_communicator if self.pipeline else None
                )
            }
            
            # Start recovery processor
            self.error_recovery["recovery_processor"].start()
            return True
            
        except Exception as e:
            logger.error(f"Error recovery startup failed: {e}")
            return False
    
    def _start_session_management(self) -> bool:
        """Start session management."""
        try:
            self.session_mgmt = {
                "archiver": SessionArchiver(),
                "manager": SessionManager(self.config["session_management"])
            }
            
            self.session_mgmt["manager"].start()
            return True
            
        except Exception as e:
            logger.error(f"Session management startup failed: {e}")
            return False
    
    def _start_monitoring(self):
        """Start integration monitoring."""
        def monitoring_loop():
            while not self.shutdown_event.is_set():
                try:
                    self._update_integration_stats()
                    self.shutdown_event.wait(self.config["monitoring"]["status_interval"])
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    self.shutdown_event.wait(60)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Integration monitoring started")
    
    def _stop_monitoring(self):
        """Stop integration monitoring."""
        if self.monitoring_thread:
            self.shutdown_event.set()
            self.monitoring_thread.join(timeout=5)
    
    def _stop_session_management(self):
        """Stop session management."""
        if self.session_mgmt and self.session_mgmt["manager"]:
            self.session_mgmt["manager"].stop()
    
    def _stop_error_recovery(self):
        """Stop error recovery systems."""
        if self.error_recovery and self.error_recovery["recovery_processor"]:
            self.error_recovery["recovery_processor"].stop()
    
    def _stop_pipeline(self):
        """Stop event processing pipeline."""
        if self.pipeline:
            self.pipeline.stop()
    
    def _stop_agent_orchestrator(self):
        """Stop agent orchestrator."""
        if self.agent_orchestrator:
            self.agent_orchestrator.stop_all_agents()
    
    def _cleanup_on_error(self):
        """Clean up resources after startup error."""
        logger.info("Cleaning up after startup error...")
        self._stop_monitoring()
        self._stop_session_management()
        self._stop_error_recovery()
        self._stop_pipeline()
        self._stop_agent_orchestrator()
    
    def _wait_for_agents_healthy(self, agent_urls: List[str], timeout: int) -> bool:
        """Wait for all agents to become healthy."""
        import capstone.agent_utils as agent_utils
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            healthy_count = 0
            
            for url in agent_urls:
                healthy, _ = agent_utils.A2ACommunicator().health_check_agent(url)
                if healthy:
                    healthy_count += 1
            
            if healthy_count == len(agent_urls):
                logger.info(f"All {len(agent_urls)} agents are healthy")
                return True
            
            logger.info(f"Waiting for agents: {healthy_count}/{len(agent_urls)} healthy")
            time.sleep(10)
        
        return False
    
    def _update_integration_stats(self):
        """Update integration statistics."""
        try:
            if self.pipeline:
                pipeline_status = self.pipeline.get_pipeline_status()
                self.integration_stats.update({
                    "total_events_processed": pipeline_status["stats"]["events_processed"],
                    "total_incidents_created": pipeline_status["stats"]["incidents_created"],
                    "total_errors": pipeline_status["stats"]["errors"]
                })
                
                # Calculate pipeline health score
                total_agents = pipeline_status["agent_health"]["total_agents"]
                healthy_agents = pipeline_status["agent_health"]["healthy_agents"]
                if total_agents > 0:
                    self.integration_stats["agent_health_score"] = healthy_agents / total_agents
            
            if self.session_mgmt:
                manager_stats = self.session_mgmt["manager"].get_stats()
                session_stats = manager_stats["session_manager"]
                self.integration_stats.update({
                    "sessions_archived": session_stats.get("archived_sessions", 0),
                    "sessions_restored": session_stats.get("restored_sessions", 0)
                })
            
            if self.error_recovery:
                dlq_stats = self.error_recovery["dead_letter_queue"].get_stats()
                self.integration_stats["recovery_attempts"] = dlq_stats.get("total_events", 0)
            
            # Update uptime
            if self.startup_time:
                self.integration_stats["uptime"] = (
                    datetime.now() - self.startup_time
                ).total_seconds()
            
            # Calculate overall health score
            health_scores = [
                self.integration_stats["agent_health_score"],
                1.0 if self.running else 0.0  # Pipeline running
            ]
            self.integration_stats["pipeline_health_score"] = sum(health_scores) / len(health_scores)
            
        except Exception as e:
            logger.error(f"Failed to update integration stats: {e}")
    
    def process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an event through the complete integration pipeline.
        
        Args:
            event_data: Event data to process
            
        Returns:
            Processing result
        """
        if not self.running or not self.pipeline:
            return {
                "success": False,
                "error": "Integration not running"
            }
        
        try:
            result = self.pipeline.process_event(event_data)
            
            # Update stats
            if result["success"]:
                self.integration_stats["total_events_processed"] += 1
                if "incident_id" in result:
                    self.integration_stats["total_incidents_created"] += 1
            else:
                self.integration_stats["total_errors"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Event processing failed: {e}")
            self.integration_stats["total_errors"] += 1
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get comprehensive integration status."""
        status = {
            "integration": {
                "running": self.running,
                "startup_time": self.integration_stats["startup_time"],
                "uptime": self.integration_stats["uptime"],
                "health_score": self.integration_stats["pipeline_health_score"]
            },
            "statistics": self.integration_stats.copy(),
            "components": {}
        }
        
        # Add component status
        if self.pipeline:
            status["components"]["pipeline"] = self.pipeline.get_pipeline_status()
        
        if self.agent_orchestrator:
            status["components"]["agents"] = self.agent_orchestrator.get_agent_status()
        
        if self.session_mgmt:
            archiver_stats = self.session_mgmt["archiver"].get_archive_stats()
            status["components"]["session_management"] = {
                "archiver": archiver_stats,
                "manager": self.session_mgmt["manager"].get_stats()
            }
        
        if self.error_recovery:
            status["components"]["error_recovery"] = {
                "retry_stats": self.error_recovery["retry_handler"].get_stats(),
                "circuit_breakers": self.error_recovery["circuit_breaker_manager"].get_all_breaker_status(),
                "dead_letter_queue": self.error_recovery["dead_letter_queue"].get_stats(),
                "recovery_processor": self.error_recovery["recovery_processor"].get_recovery_stats()
            }
        
        return status
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AgentFleet Main Integration Orchestrator")
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the complete integration"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show integration status"
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the integration"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run integration test with sample event"
    )
    parser.add_argument(
        "--config",
        help="Configuration file path"
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=0,
        help="Wait time in seconds after startup (for testing)"
    )
    
    args = parser.parse_args()
    
    # Change to capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Initialize integration
    integration = AgentFleetIntegration(args.config)
    
    if args.status:
        # Show status
        status = integration.get_integration_status()
        
        print("\nAgentFleet Integration Status")
        print("=" * 50)
        print(f"Running: {'Yes' if status['integration']['running'] else 'No'}")
        print(f"Uptime: {status['integration']['uptime']:.1f}s")
        print(f"Health Score: {status['integration']['health_score']:.2%}")
        print(f"Events Processed: {status['statistics']['total_events_processed']}")
        print(f"Incidents Created: {status['statistics']['total_incidents_created']}")
        print(f"Total Errors: {status['statistics']['total_errors']}")
        
        if 'agents' in status['components']:
            agent_status = status['components']['agents']
            healthy_agents = sum(1 for s in agent_status.values() if s['status'] == 'healthy')
            total_agents = len(agent_status)
            print(f"Agent Health: {healthy_agents}/{total_agents} healthy")
        
        print("=" * 50)
        return
    
    if args.stop:
        # Stop integration
        print("Stopping AgentFleet Integration...")
        integration.stop()
        return
    
    if args.test:
        # Run test
        print("Starting integration test...")
        
        # Start integration
        if not integration.start():
            print("❌ Failed to start integration")
            return
        
        # Wait for startup
        print("Waiting for integration to start...")
        time.sleep(10)
        
        # Test event processing
        test_event = {
            "source": "emergency",
            "content": "Multiple vehicle collision reported on I-95, multiple injuries. Fire and ambulance en route.",
            "timestamp": datetime.now().isoformat(),
            "location": "I-95",
            "severity": "HIGH"
        }
        
        print("Processing test event...")
        result = integration.process_event(test_event)
        
        if result["success"]:
            print("✅ Test event processed successfully!")
            print(f"   Session ID: {result['session_id']}")
            print(f"   Incident ID: {result['incident_id']}")
        else:
            print(f"❌ Test event processing failed: {result.get('error', 'Unknown error')}")
        
        # Show status
        status = integration.get_integration_status()
        print(f"\nFinal Status:")
        print(f"Events Processed: {status['statistics']['total_events_processed']}")
        print(f"Incidents Created: {status['statistics']['total_incidents_created']}")
        print(f"Errors: {status['statistics']['total_errors']}")
        
        # Stop integration
        integration.stop()
        return
    
    if args.start:
        # Start integration
        print("Starting AgentFleet Integration...")
        
        try:
            if integration.start():
                print("✅ AgentFleet Integration started successfully!")
                
                # Show status
                status = integration.get_integration_status()
                print(f"\nIntegration Status:")
                print(f"Health Score: {status['integration']['health_score']:.2%}")
                print(f"Components: {len(status['components'])} active")
                
                print(f"\nAgentFleet Integration is running. Press Ctrl+C to stop.")
                if args.wait > 0:
                    print(f"Running for {args.wait} seconds for testing...")
                    integration.shutdown_event.wait(args.wait)
                
                # Wait for shutdown signal
                try:
                    while not integration.shutdown_event.is_set():
                        integration.shutdown_event.wait(1)
                except KeyboardInterrupt:
                    print("\nShutting down...")
            else:
                print("❌ Failed to start AgentFleet Integration")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Integration startup error: {e}")
            sys.exit(1)
        finally:
            integration.stop()
    else:
        print("Please specify --start, --status, --stop, or --test")
        sys.exit(1)


if __name__ == "__main__":
    main()