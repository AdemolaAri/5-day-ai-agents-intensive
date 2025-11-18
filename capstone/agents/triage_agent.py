"""
Triage Agent for AgentFleet.

This agent is responsible for:
- Receiving incident briefs from the Summarizer Agent via A2A protocol
- Analyzing incident severity and classifying as LOW/MEDIUM/HIGH/CRITICAL
- Calculating priority scores (0.0 to 1.0)
- Creating job queue entries for HIGH and CRITICAL incidents
- Managing job queue operations (create, update, query)
- Forwarding triaged incidents to the Dispatcher Agent via A2A protocol

Requirements Satisfied:
- 4.1: Analyze incident content to determine severity level
- 4.2: Classify incidents as LOW, MEDIUM, HIGH, or CRITICAL
- 4.3: Create priority job entries for CRITICAL and HIGH incidents
- 4.4: Assign unique job identifier and timestamp
- 4.5: Forward triaged incident to Dispatcher Agent via A2A protocol
- 11.2: Persist jobs to SQLite database
- 11.3: Update job status with completion timestamp
"""

import os
import uuid
import logging
import time
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from capstone.models import (
    IncidentBrief,
    TriagedIncident,
    SeverityLevel,
    Job,
    JobStatus
)
from capstone.mcp_envelope import (
    MCPEnvelope,
    EnvelopeSchema,
    PayloadType,
    create_triage_envelope,
    parse_envelope
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def classify_severity_tool(
    summary: str,
    key_facts: str,
    location: str = "",
    reliability_score: float = 0.0
) -> Dict[str, Any]:
    """
    Tool function to classify incident severity.
    
    This tool analyzes the incident content and assigns a severity level:
    - CRITICAL: Immediate threat to life, major infrastructure failure, widespread impact
    - HIGH: Significant threat, infrastructure damage, regional impact
    - MEDIUM: Moderate threat, localized damage, limited impact
    - LOW: Minor threat, minimal damage, very limited impact
    
    Args:
        summary: Incident summary text
        key_facts: JSON string containing key facts
        location: Incident location
        reliability_score: Verification reliability score
        
    Returns:
        Dictionary containing severity classification and reasoning
    """
    try:
        # Parse key facts
        try:
            facts = json.loads(key_facts) if isinstance(key_facts, str) else key_facts
        except json.JSONDecodeError:
            facts = []
        
        # Initialize severity indicators
        severity_score = 0.0
        reasoning_parts = []
        
        # Analyze summary for severity keywords
        summary_lower = summary.lower()
        
        # Critical indicators
        critical_keywords = [
            'death', 'deaths', 'fatality', 'fatalities', 'killed',
            'major', 'catastrophic', 'disaster', 'emergency',
            'widespread', 'massive', 'critical', 'severe'
        ]
        critical_count = sum(1 for kw in critical_keywords if kw in summary_lower)
        if critical_count >= 2:
            severity_score += 0.4
            reasoning_parts.append(f"Multiple critical indicators found ({critical_count})")
        
        # High severity indicators
        high_keywords = [
            'fire', 'flood', 'flooding', 'explosion', 'collapse',
            'injured', 'casualties', 'damage', 'destroyed', 'evacuation'
        ]
        high_count = sum(1 for kw in high_keywords if kw in summary_lower)
        if high_count >= 2:
            severity_score += 0.3
            reasoning_parts.append(f"High severity indicators present ({high_count})")
        
        # Medium severity indicators
        medium_keywords = [
            'incident', 'accident', 'disruption', 'outage',
            'affected', 'impact', 'concern', 'alert'
        ]
        medium_count = sum(1 for kw in medium_keywords if kw in summary_lower)
        if medium_count >= 1:
            severity_score += 0.15
            reasoning_parts.append(f"Moderate impact indicators ({medium_count})")
        
        # Analyze numbers in summary (casualties, affected people, etc.)
        words = summary.split()
        for i, word in enumerate(words):
            if any(char.isdigit() for char in word):
                try:
                    # Extract number
                    num_str = ''.join(c for c in word if c.isdigit() or c == '.')
                    num = float(num_str)
                    
                    # Check context
                    context = ' '.join(words[max(0, i-2):min(len(words), i+3)]).lower()
                    
                    if any(kw in context for kw in ['death', 'killed', 'fatality']):
                        if num >= 10:
                            severity_score += 0.5
                            reasoning_parts.append(f"High casualty count: {num}")
                        elif num >= 1:
                            severity_score += 0.3
                            reasoning_parts.append(f"Casualties reported: {num}")
                    
                    elif any(kw in context for kw in ['injured', 'affected', 'evacuated']):
                        if num >= 1000:
                            severity_score += 0.3
                            reasoning_parts.append(f"Large number affected: {num}")
                        elif num >= 100:
                            severity_score += 0.2
                            reasoning_parts.append(f"Significant number affected: {num}")
                
                except ValueError:
                    continue
        
        # Factor in reliability score
        if reliability_score < 0.3:
            severity_score *= 0.7
            reasoning_parts.append("Reduced confidence due to low reliability score")
        elif reliability_score >= 0.7:
            reasoning_parts.append("High confidence in assessment")
        
        # Determine severity level
        if severity_score >= 0.7:
            severity = SeverityLevel.CRITICAL
            priority_score = min(1.0, severity_score)
        elif severity_score >= 0.5:
            severity = SeverityLevel.HIGH
            priority_score = severity_score
        elif severity_score >= 0.3:
            severity = SeverityLevel.MEDIUM
            priority_score = severity_score
        else:
            severity = SeverityLevel.LOW
            priority_score = max(0.1, severity_score)
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Standard classification based on content analysis"
        
        logger.info(f"Classified incident as {severity.value} (priority: {priority_score:.2f})")
        
        return {
            "success": True,
            "severity": severity.value,
            "priority_score": priority_score,
            "reasoning": reasoning,
            "severity_score": severity_score
        }
    
    except Exception as e:
        logger.error(f"Error classifying severity: {e}")
        return {
            "success": False,
            "error": str(e),
            "severity": SeverityLevel.MEDIUM.value,
            "priority_score": 0.5,
            "reasoning": "Error during classification, defaulting to MEDIUM"
        }


def create_job_tool(
    incident_id: str,
    severity: str,
    priority_score: float,
    db_path: str
) -> Dict[str, Any]:
    """
    Tool function to create a job queue entry.
    
    Creates a job entry in the SQLite database for HIGH and CRITICAL incidents.
    Jobs are used to track long-running triage operations and ensure
    incidents are properly processed.
    
    Args:
        incident_id: Unique incident identifier
        severity: Severity level (LOW/MEDIUM/HIGH/CRITICAL)
        priority_score: Priority score (0.0 to 1.0)
        db_path: Path to SQLite database
        
    Returns:
        Dictionary containing job creation result
    """
    try:
        # Only create jobs for HIGH and CRITICAL incidents
        if severity not in [SeverityLevel.HIGH.value, SeverityLevel.CRITICAL.value]:
            logger.info(f"Skipping job creation for {severity} severity incident")
            return {
                "success": True,
                "job_created": False,
                "reason": f"Jobs only created for HIGH and CRITICAL incidents (severity: {severity})"
            }
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job entry
        job = Job(
            job_id=job_id,
            incident_id=incident_id,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            result=None
        )
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert job
        cursor.execute("""
            INSERT INTO jobs (job_id, incident_id, status, created_at, updated_at, result)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job.job_id,
            job.incident_id,
            job.status.value,
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
            json.dumps(job.result) if job.result else None
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created job {job_id} for incident {incident_id} (severity: {severity})")
        
        return {
            "success": True,
            "job_created": True,
            "job_id": job_id,
            "incident_id": incident_id,
            "status": JobStatus.PENDING.value,
            "created_at": job.created_at.isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        return {
            "success": False,
            "error": str(e),
            "job_created": False
        }


def update_job_status_tool(
    job_id: str,
    status: str,
    result: Optional[str] = None,
    db_path: str = "./capstone/data/agentfleet.db"
) -> Dict[str, Any]:
    """
    Tool function to update job status.
    
    Updates the status of an existing job in the database.
    
    Args:
        job_id: Job identifier
        status: New status (PENDING/PROCESSING/COMPLETED/FAILED)
        result: Optional result data as JSON string
        db_path: Path to SQLite database
        
    Returns:
        Dictionary containing update result
    """
    try:
        # Validate status
        try:
            job_status = JobStatus(status)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid status: {status}"
            }
        
        # Parse result if provided
        result_data = None
        if result:
            try:
                result_data = json.loads(result) if isinstance(result, str) else result
            except json.JSONDecodeError:
                result_data = {"raw": result}
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Update job
        cursor.execute("""
            UPDATE jobs
            SET status = ?, updated_at = ?, result = ?
            WHERE job_id = ?
        """, (
            job_status.value,
            datetime.utcnow().isoformat(),
            json.dumps(result_data) if result_data else None,
            job_id
        ))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected == 0:
            logger.warning(f"Job {job_id} not found")
            return {
                "success": False,
                "error": f"Job {job_id} not found"
            }
        
        logger.info(f"Updated job {job_id} to status {status}")
        
        return {
            "success": True,
            "job_id": job_id,
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error updating job status: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def query_jobs_tool(
    status: Optional[str] = None,
    incident_id: Optional[str] = None,
    limit: int = 100,
    db_path: str = "./capstone/data/agentfleet.db"
) -> Dict[str, Any]:
    """
    Tool function to query jobs from the database.
    
    Args:
        status: Optional status filter
        incident_id: Optional incident ID filter
        limit: Maximum number of results
        db_path: Path to SQLite database
        
    Returns:
        Dictionary containing query results
    """
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT job_id, incident_id, status, created_at, updated_at, result FROM jobs WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if incident_id:
            query += " AND incident_id = ?"
            params.append(incident_id)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Format results
        jobs = []
        for row in rows:
            jobs.append({
                "job_id": row[0],
                "incident_id": row[1],
                "status": row[2],
                "created_at": row[3],
                "updated_at": row[4],
                "result": json.loads(row[5]) if row[5] else None
            })
        
        conn.close()
        
        logger.info(f"Found {len(jobs)} jobs")
        
        return {
            "success": True,
            "jobs": jobs,
            "count": len(jobs)
        }
    
    except Exception as e:
        logger.error(f"Error querying jobs: {e}")
        return {
            "success": False,
            "error": str(e),
            "jobs": []
        }


def create_forward_to_dispatcher_tool(dispatcher_url: str):
    """
    Factory function to create a forward_to_dispatcher tool.
    
    Args:
        dispatcher_url: URL of the Dispatcher Agent
        
    Returns:
        Tool function for forwarding to Dispatcher Agent
    """
    def forward_to_dispatcher_tool(
        envelope_json: str
    ) -> Dict[str, Any]:
        """
        Tool function to forward triaged incidents to the Dispatcher Agent.
        
        Implements A2A protocol communication with retry logic and exponential backoff.
        
        Args:
            envelope_json: JSON string containing MCP envelope with triaged incident
            
        Returns:
            Dictionary containing the response from Dispatcher Agent
        """
        import httpx
        
        max_retries = 3
        initial_delay = 1.0
        backoff_multiplier = 2.0
        max_delay = 10.0
        
        try:
            envelope_data = json.loads(envelope_json)
            
            # Validate envelope before forwarding
            is_valid, error_msg = parse_envelope(envelope_data)
            if not is_valid:
                logger.error(f"Invalid envelope: {error_msg}")
                return {
                    "success": False,
                    "error": f"Invalid envelope: {error_msg}"
                }
            
            logger.info("Forwarding to Dispatcher Agent via A2A protocol")
            
            # Retry logic with exponential backoff
            for attempt in range(max_retries):
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            f"{dispatcher_url}/tasks",
                            json=envelope_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            logger.info(f"Successfully forwarded to Dispatcher Agent")
                            return {
                                "success": True,
                                "response": response.json(),
                                "status_code": response.status_code,
                                "attempts": attempt + 1
                            }
                        else:
                            logger.warning(f"Dispatcher Agent returned status {response.status_code}")
                            if attempt == max_retries - 1:
                                return {
                                    "success": False,
                                    "error": f"HTTP {response.status_code}",
                                    "response": response.text,
                                    "attempts": attempt + 1
                                }
                
                except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
                    logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {e}")
                    
                    if attempt == max_retries - 1:
                        return {
                            "success": False,
                            "error": f"Connection failed after {max_retries} attempts",
                            "details": str(e),
                            "attempts": max_retries
                        }
                    
                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (backoff_multiplier ** attempt), max_delay)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
            
            return {
                "success": False,
                "error": "Max retries exceeded"
            }
        
        except Exception as e:
            logger.error(f"Error forwarding to dispatcher: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    return forward_to_dispatcher_tool


class TriageAgent:
    """
    Triage Agent for incident severity classification and job queue management.
    
    Responsibilities:
    - Classify incident severity (LOW/MEDIUM/HIGH/CRITICAL)
    - Calculate priority scores (0.0 to 1.0)
    - Create job queue entries for HIGH and CRITICAL incidents
    - Manage job queue operations
    - Forward triaged incidents to Dispatcher Agent
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-lite",
        dispatcher_url: str = "http://localhost:8005",
        db_path: str = "./capstone/data/agentfleet.db"
    ):
        """
        Initialize the Triage Agent.
        
        Args:
            model_name: Name of the Gemini model to use
            dispatcher_url: URL of the Dispatcher Agent for A2A communication
            db_path: Path to SQLite database
        """
        self.model_name = model_name
        self.agent_name = "triage_agent"
        self.dispatcher_url = dispatcher_url
        self.db_path = db_path
        
        # Initialize Gemini client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        
        # Agent instruction
        self.instruction = """You are the Triage Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive incident briefs from the Summarizer Agent via A2A protocol
2. Analyze incident content to determine severity level
3. Classify incidents as LOW, MEDIUM, HIGH, or CRITICAL based on:
   - Threat to life or safety
   - Infrastructure impact
   - Geographic scope
   - Number of people affected
   - Urgency of response needed
4. Calculate priority scores (0.0 to 1.0) for incident ordering
5. Create job queue entries for HIGH and CRITICAL incidents
6. Forward triaged incidents to the Dispatcher Agent

Severity Classification Guidelines:
- CRITICAL: Immediate threat to life, major infrastructure failure, widespread impact (>1000 affected)
- HIGH: Significant threat, infrastructure damage, regional impact (100-1000 affected)
- MEDIUM: Moderate threat, localized damage, limited impact (10-100 affected)
- LOW: Minor threat, minimal damage, very limited impact (<10 affected)

When processing incidents:
- Use the classify_severity tool to analyze and classify incidents
- Use the create_job tool to create job entries for HIGH and CRITICAL incidents
- Use the forward_to_dispatcher tool to send triaged incidents to the next agent
- Always provide clear reasoning for severity assignments
- Consider reliability scores when making classifications

Be decisive and consistent in your classifications.
Prioritize human safety and infrastructure integrity.
"""
        
        # Define tools
        self.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="classify_severity",
                        description="Classify incident severity as LOW, MEDIUM, HIGH, or CRITICAL with priority score",
                        parameters={
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Incident summary text"
                                },
                                "key_facts": {
                                    "type": "string",
                                    "description": "JSON string containing key facts"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "Incident location"
                                },
                                "reliability_score": {
                                    "type": "number",
                                    "description": "Verification reliability score (0.0 to 1.0)"
                                }
                            },
                            "required": ["summary", "key_facts"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="create_job",
                        description="Create a job queue entry for HIGH or CRITICAL incidents",
                        parameters={
                            "type": "object",
                            "properties": {
                                "incident_id": {
                                    "type": "string",
                                    "description": "Unique incident identifier"
                                },
                                "severity": {
                                    "type": "string",
                                    "description": "Severity level (LOW/MEDIUM/HIGH/CRITICAL)"
                                },
                                "priority_score": {
                                    "type": "number",
                                    "description": "Priority score (0.0 to 1.0)"
                                },
                                "db_path": {
                                    "type": "string",
                                    "description": "Path to SQLite database"
                                }
                            },
                            "required": ["incident_id", "severity", "priority_score", "db_path"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="update_job_status",
                        description="Update the status of an existing job",
                        parameters={
                            "type": "object",
                            "properties": {
                                "job_id": {
                                    "type": "string",
                                    "description": "Job identifier"
                                },
                                "status": {
                                    "type": "string",
                                    "description": "New status (PENDING/PROCESSING/COMPLETED/FAILED)"
                                },
                                "result": {
                                    "type": "string",
                                    "description": "Optional result data as JSON string"
                                },
                                "db_path": {
                                    "type": "string",
                                    "description": "Path to SQLite database"
                                }
                            },
                            "required": ["job_id", "status", "db_path"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="query_jobs",
                        description="Query jobs from the database with optional filters",
                        parameters={
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "description": "Optional status filter"
                                },
                                "incident_id": {
                                    "type": "string",
                                    "description": "Optional incident ID filter"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of results",
                                    "default": 100
                                },
                                "db_path": {
                                    "type": "string",
                                    "description": "Path to SQLite database"
                                }
                            },
                            "required": ["db_path"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="forward_to_dispatcher",
                        description="Forward triaged incident envelope to the Dispatcher Agent via A2A protocol",
                        parameters={
                            "type": "object",
                            "properties": {
                                "envelope_json": {
                                    "type": "string",
                                    "description": "JSON string containing the MCP envelope with triaged incident"
                                }
                            },
                            "required": ["envelope_json"]
                        }
                    )
                ]
            )
        ]
        
        # Create the forward_to_dispatcher tool
        self.forward_to_dispatcher_tool = create_forward_to_dispatcher_tool(
            self.dispatcher_url
        )
        
        logger.info(f"Initialized Triage Agent with model {model_name}")
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool function."""
        if tool_name == "classify_severity":
            return classify_severity_tool(**tool_args)
        elif tool_name == "create_job":
            return create_job_tool(**tool_args)
        elif tool_name == "update_job_status":
            return update_job_status_tool(**tool_args)
        elif tool_name == "query_jobs":
            return query_jobs_tool(**tool_args)
        elif tool_name == "forward_to_dispatcher":
            return self.forward_to_dispatcher_tool(**tool_args)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    def process_message(self, message: str) -> str:
        """
        Process a message using the agent.
        
        Args:
            message: User message or task description
            
        Returns:
            Agent response
        """
        try:
            # Create chat session
            chat = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=self.instruction,
                    tools=self.tools,
                    temperature=0.1
                )
            )
            
            # Send message
            response = chat.send_message(message)
            
            # Handle tool calls
            while response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                
                # Check if it's a function call
                if hasattr(part, 'function_call') and part.function_call:
                    function_call = part.function_call
                    tool_name = function_call.name
                    tool_args = dict(function_call.args)
                    
                    logger.info(f"Executing tool: {tool_name}")
                    
                    # Execute tool
                    tool_result = self._execute_tool(tool_name, tool_args)
                    
                    # Send tool response back
                    response = chat.send_message(
                        types.Content(
                            parts=[
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        name=tool_name,
                                        response=tool_result
                                    )
                                )
                            ]
                        )
                    )
                else:
                    # Text response
                    if hasattr(part, 'text'):
                        return part.text
                    break
            
            # Extract final text response
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text'):
                        return part.text
            
            return "No response generated"
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return f"Error: {str(e)}"
    
    def process_incident_envelope(self, envelope_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incident brief envelope from the Summarizer Agent.
        
        Args:
            envelope_data: MCP envelope containing incident brief
            
        Returns:
            Processing result with triaged incident
        """
        try:
            # Parse and validate envelope
            envelope, error_msg = parse_envelope(envelope_data)
            if not envelope:
                logger.error(f"Invalid envelope: {error_msg}")
                return {
                    "success": False,
                    "error": f"Invalid envelope: {error_msg}"
                }
            
            # Extract incident data
            incident_data = envelope.payload.get("data", {})
            incident_id = incident_data.get("incident_id", "unknown")
            summary = incident_data.get("summary", "")
            key_facts = incident_data.get("key_facts", [])
            location = incident_data.get("location", "")
            
            # Create processing message
            message = f"""Process this incident brief for triage:

Incident ID: {incident_id}
Summary: {summary}
Location: {location}
Key Facts: {json.dumps(key_facts)}

Full Incident Data: {json.dumps(incident_data)}

Tasks:
1. Classify the severity level (LOW/MEDIUM/HIGH/CRITICAL)
2. Calculate priority score (0.0 to 1.0)
3. Create job entry if severity is HIGH or CRITICAL
4. Create triaged incident envelope
5. Forward to Dispatcher Agent

Database Path: {self.db_path}
Session ID: {envelope.session_id}
"""
            
            # Process with agent
            response = self.process_message(message)
            
            return {
                "success": True,
                "response": response,
                "session_id": envelope.session_id,
                "incident_id": incident_id
            }
        
        except Exception as e:
            logger.error(f"Error processing incident envelope: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def create_triage_agent(
    model_name: str = "gemini-2.0-flash-lite",
    dispatcher_url: str = "http://localhost:8005",
    db_path: str = "./capstone/data/agentfleet.db"
) -> TriageAgent:
    """
    Factory function to create a Triage Agent instance.
    
    Args:
        model_name: Name of the Gemini model to use
        dispatcher_url: URL of the Dispatcher Agent for A2A communication
        db_path: Path to SQLite database
        
    Returns:
        TriageAgent instance
    """
    return TriageAgent(
        model_name=model_name,
        dispatcher_url=dispatcher_url,
        db_path=db_path
    )
