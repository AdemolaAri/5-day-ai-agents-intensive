#!/usr/bin/env python3
"""
AgentFleet Error Recovery and Circuit Breaker System

This module implements comprehensive error recovery mechanisms including
A2A retry logic, circuit breaker patterns, dead letter queue management,
and recovery job processing for failed events.

Requirements Satisfied:
- 13.2: Implement error recovery mechanisms with A2A retry logic and circuit breaker
- 6.5: Circuit breaker for failing agents with automatic recovery
- 11.4: Dead letter queue for failed events with recovery processing

Usage:
    # As a module
    from capstone.error_recovery import A2ARetryHandler, CircuitBreakerManager, DeadLetterQueue
    
    # As a standalone service
    python error_recovery.py --serve
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Add capstone to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_utils import A2ACommunicator, A2ARequest, A2AResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FailedEvent:
    """Failed event for dead letter queue."""
    event_id: str
    original_payload: Dict[str, Any]
    target_agent: str
    target_url: str
    failure_reason: str
    failure_count: int
    first_failure: datetime
    last_failure: datetime
    retry_after: Optional[datetime] = None
    status: str = "pending"  # pending, retrying, failed, recovered
    metadata: Dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """Circuit breaker implementation for agent failure protection."""
    
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


class A2ARetryHandler:
    """
    Enhanced A2A retry handler with exponential backoff and jitter.
    
    Features:
    - Configurable retry strategies
    - Exponential backoff with jitter
    - Circuit breaker integration
    - Retry attempt tracking
    - Dead letter queue integration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize retry handler.
        
        Args:
            config: Retry configuration
        """
        self.config = config or self._default_config()
        self.communicator = A2ACommunicator()
        self.dead_letter_queue = DeadLetterQueue()
        
        # Retry statistics
        self.stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "dead_letter_queue_size": 0
        }
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default retry configuration."""
        return {
            "max_retries": 3,
            "initial_delay": 1.0,
            "backoff_multiplier": 2.0,
            "max_delay": 30.0,
            "jitter": 0.1,
            "timeout": 30,
            "enable_dead_letter_queue": True
        }
    
    def execute_with_retry(self, request: A2ARequest) -> A2AResponse:
        """
        Execute A2A request with retry logic.
        
        Args:
            request: A2A request configuration
            
        Returns:
            A2A response with retry information
        """
        last_error = None
        
        for attempt in range(request.max_retries + 1):
            try:
                # Execute the request
                response = self.communicator.send_a2a_request(request)
                
                if response.success:
                    # Update successful retry stats
                    if attempt > 0:
                        self.stats["successful_retries"] += 1
                    
                    logger.info(f"A2A request successful after {attempt} retries")
                    return response
                
                else:
                    last_error = response.error
                    logger.warning(f"A2A attempt {attempt + 1} failed: {response.error}")
                    
                    # Don't retry on the last attempt
                    if attempt < request.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.info(f"Retrying in {delay:.2f} seconds...")
                        time.sleep(delay)
                        
                        self.stats["total_retries"] += 1
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"A2A attempt {attempt + 1} threw exception: {e}")
                
                if attempt < request.max_retries:
                    delay = self._calculate_delay(attempt)
                    time.sleep(delay)
                    
                    self.stats["total_retries"] += 1
        
        # All retries exhausted
        self.stats["failed_retries"] += 1
        
        # Add to dead letter queue if enabled
        if self.config["enable_dead_letter_queue"]:
            failed_event = FailedEvent(
                event_id=str(uuid.uuid4()),
                original_payload=request.envelope,
                target_agent=self._extract_agent_name(request.agent_url),
                target_url=request.agent_url,
                failure_reason=f"All {request.max_retries + 1} attempts failed: {last_error}",
                failure_count=request.max_retries + 1,
                first_failure=datetime.now(),
                last_failure=datetime.now(),
                status="pending"
            )
            
            self.dead_letter_queue.add_failed_event(failed_event)
            self.stats["dead_letter_queue_size"] = self.dead_letter_queue.get_queue_size()
        
        logger.error(f"A2A request failed after {request.max_retries + 1} attempts")
        
        return A2AResponse(
            success=False,
            status_code=0,
            error=f"All {request.max_retries + 1} attempts failed. Last error: {last_error}"
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = min(
            self.config["initial_delay"] * (self.config["backoff_multiplier"] ** attempt),
            self.config["max_delay"]
        )
        
        # Add jitter
        jitter_amount = delay * self.config["jitter"]
        delay = delay + (jitter_amount * (0.5 - time.time() % 1))
        
        return max(delay, 0.1)  # Minimum 100ms delay
    
    def _extract_agent_name(self, url: str) -> str:
        """Extract agent name from URL."""
        # Simple mapping for now
        port_mapping = {
            "8001": "ingest",
            "8002": "verifier",
            "8003": "summarizer", 
            "8004": "triage",
            "8005": "dispatcher"
        }
        
        for port, agent_name in port_mapping.items():
            if f":{port}" in url:
                return agent_name
        
        return "unknown"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics."""
        self.stats["dead_letter_queue_size"] = self.dead_letter_queue.get_queue_size()
        return self.stats.copy()


class CircuitBreakerManager:
    """
    Circuit breaker manager for multiple agents.
    
    Features:
    - Per-agent circuit breakers
    - Automatic state transitions
    - Health monitoring integration
    - Metrics collection
    - Recovery notifications
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize circuit breaker manager.
        
        Args:
            config: Circuit breaker configuration
        """
        self.config = config or self._default_config()
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
        
        # Circuit breaker statistics
        self.stats = {
            "breakers_created": 0,
            "breakers_opened": 0,
            "breakers_recovered": 0,
            "requests_blocked": 0,
            "total_failures": 0
        }
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default circuit breaker configuration."""
        return {
            "failure_threshold": 5,
            "recovery_timeout": 60,
            "half_open_max_calls": 3,
            "monitoring_interval": 30
        }
    
    def get_breaker(self, agent_id: str) -> 'CircuitBreaker':
        """Get or create circuit breaker for agent."""
        with self._lock:
            if agent_id not in self.breakers:
                self.breakers[agent_id] = CircuitBreaker(
                    failure_threshold=self.config["failure_threshold"],
                    timeout=self.config["recovery_timeout"]
                )
                self.stats["breakers_created"] += 1
                logger.info(f"Created circuit breaker for agent {agent_id}")
            
            return self.breakers[agent_id]
    
    def execute_with_circuit_breaker(self, agent_id: str, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            agent_id: Agent identifier
            func: Function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit breaker is open or function fails
        """
        breaker = self.get_breaker(agent_id)
        
        try:
            # Execute with circuit breaker
            result = breaker.call(func, *args, **kwargs)
            
            # Update success statistics
            if breaker.state == "HALF_OPEN":
                self.stats["breakers_recovered"] += 1
                logger.info(f"Circuit breaker for {agent_id} recovered")
            
            return result
            
        except Exception as e:
            # Update failure statistics
            self.stats["total_failures"] += 1
            
            # Check if circuit breaker opened
            if breaker.state == "OPEN":
                self.stats["requests_blocked"] += 1
                logger.warning(f"Request to {agent_id} blocked by circuit breaker")
            
            raise
    
    def get_breaker_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker status for agent."""
        breaker = self.breakers.get(agent_id)
        if not breaker:
            return None
        
        return {
            "agent_id": agent_id,
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "last_failure": breaker.last_failure_time,
            "threshold": breaker.failure_threshold,
            "timeout": breaker.timeout
        }
    
    def get_all_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        with self._lock:
            return {
                agent_id: self.get_breaker_status(agent_id)
                for agent_id in self.breakers
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return self.stats.copy()


class DeadLetterQueue:
    """
    Dead letter queue for managing failed events.
    
    Features:
    - Persistent storage of failed events
    - Retry scheduling with exponential backoff
    - Recovery job processing
    - Metrics and monitoring
    - Cleanup and archiving
    """
    
    def __init__(self, db_path: str = "data/dead_letter_queue.db"):
        """
        Initialize dead letter queue.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._lock = threading.RLock()
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        
        # Recovery processing
        self.recovery_enabled = True
        self.recovery_thread = None
        self.recovery_interval = 300  # 5 minutes
    
    def _init_database(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failed_events (
                    event_id TEXT PRIMARY KEY,
                    original_payload TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    failure_reason TEXT NOT NULL,
                    failure_count INTEGER NOT NULL,
                    first_failure TEXT NOT NULL,
                    last_failure TEXT NOT NULL,
                    retry_after TEXT,
                    status TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_failed_events_status 
                ON failed_events(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_failed_events_retry_after 
                ON failed_events(retry_after)
            """)
    
    def add_failed_event(self, failed_event: FailedEvent):
        """Add failed event to dead letter queue."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO failed_events 
                    (event_id, original_payload, target_agent, target_url, 
                     failure_reason, failure_count, first_failure, last_failure,
                     retry_after, status, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    failed_event.event_id,
                    json.dumps(failed_event.original_payload),
                    failed_event.target_agent,
                    failed_event.target_url,
                    failed_event.failure_reason,
                    failed_event.failure_count,
                    failed_event.first_failure.isoformat(),
                    failed_event.last_failure.isoformat(),
                    failed_event.retry_after.isoformat() if failed_event.retry_after else None,
                    failed_event.status,
                    json.dumps(failed_event.metadata)
                ))
    
    def get_pending_events(self, limit: int = 100) -> List[FailedEvent]:
        """Get pending events for retry."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT event_id, original_payload, target_agent, target_url,
                           failure_reason, failure_count, first_failure, last_failure,
                           retry_after, status, metadata
                    FROM failed_events 
                    WHERE status = 'pending' 
                       OR (status = 'retrying' AND retry_after <= ?)
                    ORDER BY last_failure
                    LIMIT ?
                """, (datetime.now().isoformat(), limit))
                
                events = []
                for row in cursor.fetchall():
                    events.append(self._row_to_failed_event(row))
                
                return events
    
    def update_event_status(self, event_id: str, status: str, retry_after: Optional[datetime] = None):
        """Update event status."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE failed_events 
                    SET status = ?, retry_after = ?
                    WHERE event_id = ?
                """, (status, retry_after.isoformat() if retry_after else None, event_id))
    
    def remove_event(self, event_id: str):
        """Remove event from dead letter queue."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM failed_events WHERE event_id = ?", (event_id,))
    
    def get_queue_size(self) -> int:
        """Get total number of events in queue."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM failed_events WHERE status IN ('pending', 'retrying')")
                return cursor.fetchone()[0]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Count by status
                cursor = conn.execute("""
                    SELECT status, COUNT(*) 
                    FROM failed_events 
                    GROUP BY status
                """)
                
                status_counts = dict(cursor.fetchall())
                
                # Get oldest failure
                cursor = conn.execute("""
                    SELECT MIN(first_failure) FROM failed_events
                """)
                oldest_failure = cursor.fetchone()[0]
                
                return {
                    "total_events": sum(status_counts.values()),
                    "by_status": status_counts,
                    "oldest_failure": oldest_failure
                }
    
    def _row_to_failed_event(self, row) -> FailedEvent:
        """Convert database row to FailedEvent object."""
        return FailedEvent(
            event_id=row[0],
            original_payload=json.loads(row[1]),
            target_agent=row[2],
            target_url=row[3],
            failure_reason=row[4],
            failure_count=row[5],
            first_failure=datetime.fromisoformat(row[6]),
            last_failure=datetime.fromisoformat(row[7]),
            retry_after=datetime.fromisoformat(row[8]) if row[8] else None,
            status=row[9],
            metadata=json.loads(row[10]) if row[10] else {}
        )


class RecoveryJobProcessor:
    """
    Background processor for recovering failed events from dead letter queue.
    
    Features:
    - Scheduled retry processing
    - Exponential backoff for retries
    - Success/failure tracking
    - Automatic cleanup of resolved events
    """
    
    def __init__(self, dead_letter_queue: DeadLetterQueue, communicator: A2ACommunicator):
        """
        Initialize recovery job processor.
        
        Args:
            dead_letter_queue: Dead letter queue instance
            communicator: A2A communicator instance
        """
        self.dead_letter_queue = dead_letter_queue
        self.communicator = communicator
        self.running = False
        self.processor_thread = None
        
        # Recovery configuration
        self.max_recovery_attempts = 5
        self.recovery_backoff_base = 300  # 5 minutes
        self.recovery_interval = 300  # 5 minutes
    
    def start(self):
        """Start recovery job processor."""
        if self.running:
            logger.warning("Recovery job processor already running")
            return
        
        self.running = True
        self.processor_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.processor_thread.start()
        
        logger.info("Recovery job processor started")
    
    def stop(self):
        """Stop recovery job processor."""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=10)
        
        logger.info("Recovery job processor stopped")
    
    def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                self._process_recovery_jobs()
                time.sleep(self.recovery_interval)
            except Exception as e:
                logger.error(f"Error in recovery job processor: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _process_recovery_jobs(self):
        """Process recovery jobs from dead letter queue."""
        pending_events = self.dead_letter_queue.get_pending_events(limit=10)
        
        for failed_event in pending_events:
            logger.info(f"Attempting recovery for event {failed_event.event_id}")
            
            if failed_event.failure_count >= self.max_recovery_attempts:
                # Max attempts reached, mark as failed
                self.dead_letter_queue.update_event_status(failed_event.event_id, "failed")
                logger.warning(f"Event {failed_event.event_id} exceeded max recovery attempts")
                continue
            
            try:
                # Calculate retry delay
                retry_delay = self.recovery_backoff_base * (2 ** (failed_event.failure_count - 1))
                retry_after = datetime.now() + timedelta(seconds=retry_delay)
                
                # Update event for next retry
                self.dead_letter_queue.update_event_status(
                    failed_event.event_id, 
                    "retrying", 
                    retry_after
                )
                
                # Attempt recovery
                request = A2ARequest(
                    agent_url=failed_event.target_url,
                    envelope=failed_event.original_payload,
                    timeout=30,
                    max_retries=1  # Single retry for recovery
                )
                
                response = self.communicator.send_a2a_request(request)
                
                if response.success:
                    # Recovery successful
                    self.dead_letter_queue.remove_event(failed_event.event_id)
                    logger.info(f"Successfully recovered event {failed_event.event_id}")
                else:
                    # Recovery failed, increment failure count
                    failed_event.failure_count += 1
                    failed_event.last_failure = datetime.now()
                    failed_event.failure_reason = f"Recovery attempt failed: {response.error}"
                    
                    self.dead_letter_queue.add_failed_event(failed_event)
                    logger.info(f"Recovery attempt {failed_event.failure_count} failed for event {failed_event.event_id}")
            
            except Exception as e:
                logger.error(f"Recovery processing error for event {failed_event.event_id}: {e}")
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery processing statistics."""
        dlq_stats = self.dead_letter_queue.get_stats()
        
        return {
            "processor_running": self.running,
            "queue_stats": dlq_stats,
            "recovery_interval": self.recovery_interval,
            "max_recovery_attempts": self.max_recovery_attempts,
            "backoff_base": self.recovery_backoff_base
        }


def main():
    """Main entry point for standalone usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentFleet Error Recovery System")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run as recovery service with background processing"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show error recovery status"
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
    
    # Initialize components
    retry_handler = A2ARetryHandler(config)
    circuit_breaker_manager = CircuitBreakerManager(config)
    dead_letter_queue = DeadLetterQueue()
    recovery_processor = RecoveryJobProcessor(dead_letter_queue, A2ACommunicator())
    
    if args.status:
        # Show status
        print("\nError Recovery System Status:")
        print("=" * 50)
        
        print("Retry Handler Stats:")
        retry_stats = retry_handler.get_stats()
        for key, value in retry_stats.items():
            print(f"  {key}: {value}")
        
        print("\nCircuit Breaker Stats:")
        cb_stats = circuit_breaker_manager.get_stats()
        for key, value in cb_stats.items():
            print(f"  {key}: {value}")
        
        print("\nDead Letter Queue Stats:")
        dlq_stats = dead_letter_queue.get_stats()
        for key, value in dlq_stats.items():
            print(f"  {key}: {value}")
        
        print("\nRecovery Processor Stats:")
        recovery_stats = recovery_processor.get_recovery_stats()
        for key, value in recovery_stats.items():
            print(f"  {key}: {value}")
        
        print("=" * 50)
        return
    
    if args.serve:
        # Start recovery service
        print("Starting Error Recovery Service...")
        
        try:
            # Start recovery processor
            recovery_processor.start()
            
            print("Error Recovery Service running. Press Ctrl+C to stop.")
            
            # Run indefinitely
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down Error Recovery Service...")
                
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            recovery_processor.stop()
    else:
        print("Please specify --serve or --status")
        sys.exit(1)


if __name__ == "__main__":
    main()