"""
Dispatcher Agent for AgentFleet.

This agent is responsible for:
- Receiving triaged incidents from the Triage Agent via A2A protocol
- Generating recommended actions with specific steps, responsible parties, and timelines
- Creating communication templates for HIGH and CRITICAL incidents
- Persisting complete incident data to SQLite database
- Updating job status to COMPLETED
- Notifying the dashboard of new incidents

Requirements Satisfied:
- 5.1: Generate list of recommended actions
- 5.2: Include specific steps, responsible parties, and timelines
- 5.3: Generate communication templates for HIGH/CRITICAL incidents
- 5.4: Persist incident record with all metadata to database
- 5.5: Make incident available to Operator Dashboard
- 11.3: Update job status with completion timestamp
- 11.5: Implement full incident data serialization
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
    TriagedIncident,
    DispatchedIncident,
    Action,
    IncidentStatus,
    SeverityLevel,
    JobStatus
)
from capstone.mcp_envelope import (
    MCPEnvelope,
    EnvelopeSchema,
    PayloadType,
    create_dispatch_envelope,
    parse_envelope
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# In-memory cache for dashboard access
INCIDENT_CACHE: Dict[str, Dict[str, Any]] = {}


def generate_actions_tool(
    incident_id: str,
    summary: str,
    severity: str,
    location: str = "",
    key_facts: str = ""
) -> Dict[str, Any]:
    """
    Tool function to generate recommended actions for incident response.
    
    Generates specific, actionable recommendations with:
    - Clear action descriptions
    - Responsible parties
    - Expected timelines
    
    Args:
        incident_id: Unique incident identifier
        summary: Incident summary
        severity: Severity level (LOW/MEDIUM/HIGH/CRITICAL)
        location: Incident location
        key_facts: JSON string containing key facts
        
    Returns:
        Dictionary containing recommended actions
    """
    try:
        # Parse key facts
        try:
            facts = json.loads(key_facts) if isinstance(key_facts, str) else key_facts
        except json.JSONDecodeError:
            facts = []
        
        actions = []
        
        # Generate actions based on severity
        if severity == SeverityLevel.CRITICAL.value:
            actions.extend([
                {
                    "action": "Activate emergency response team immediately",
                    "responsible": "Emergency Operations Center",
                    "timeline": "Immediate (0-15 minutes)"
                },
                {
                    "action": "Establish incident command post and communication channels",
                    "responsible": "Incident Commander",
                    "timeline": "Within 30 minutes"
                },
                {
                    "action": "Deploy first responders to affected location",
                    "responsible": "Emergency Services Coordinator",
                    "timeline": "Within 15-30 minutes"
                },
                {
                    "action": "Initiate evacuation procedures if necessary",
                    "responsible": "Public Safety Officer",
                    "timeline": "Within 30-60 minutes"
                },
                {
                    "action": "Notify senior leadership and relevant government agencies",
                    "responsible": "Communications Director",
                    "timeline": "Within 15 minutes"
                }
            ])
        
        elif severity == SeverityLevel.HIGH.value:
            actions.extend([
                {
                    "action": "Alert emergency response team and place on standby",
                    "responsible": "Emergency Operations Center",
                    "timeline": "Within 30 minutes"
                },
                {
                    "action": "Dispatch assessment team to evaluate situation",
                    "responsible": "Field Operations Manager",
                    "timeline": "Within 1 hour"
                },
                {
                    "action": "Coordinate with local authorities and emergency services",
                    "responsible": "Liaison Officer",
                    "timeline": "Within 1 hour"
                },
                {
                    "action": "Prepare resources and equipment for potential deployment",
                    "responsible": "Logistics Coordinator",
                    "timeline": "Within 2 hours"
                }
            ])
        
        elif severity == SeverityLevel.MEDIUM.value:
            actions.extend([
                {
                    "action": "Monitor situation for escalation",
                    "responsible": "Operations Center",
                    "timeline": "Continuous monitoring"
                },
                {
                    "action": "Conduct preliminary assessment and gather additional information",
                    "responsible": "Duty Officer",
                    "timeline": "Within 2-4 hours"
                },
                {
                    "action": "Notify relevant stakeholders and departments",
                    "responsible": "Communications Team",
                    "timeline": "Within 4 hours"
                }
            ])
        
        else:  # LOW
            actions.extend([
                {
                    "action": "Log incident for record keeping and trend analysis",
                    "responsible": "Operations Center",
                    "timeline": "Within 24 hours"
                },
                {
                    "action": "Review and update standard operating procedures if needed",
                    "responsible": "Planning Section",
                    "timeline": "Within 1 week"
                }
            ])
        
        # Add location-specific actions if location is provided
        if location:
            actions.append({
                "action": f"Coordinate with local authorities in {location}",
                "responsible": "Regional Coordinator",
                "timeline": "As appropriate for severity level"
            })
        
        logger.info(f"Generated {len(actions)} recommended actions for incident {incident_id}")
        
        return {
            "success": True,
            "actions": actions,
            "count": len(actions)
        }
    
    except Exception as e:
        logger.error(f"Error generating actions: {e}")
        return {
            "success": False,
            "error": str(e),
            "actions": []
        }


def create_communication_template_tool(
    incident_id: str,
    summary: str,
    severity: str,
    location: str = "",
    actions: str = ""
) -> Dict[str, Any]:
    """
    Tool function to create communication templates for stakeholder notification.
    
    Templates are generated for HIGH and CRITICAL incidents to ensure
    consistent and professional communication with stakeholders.
    
    Args:
        incident_id: Unique incident identifier
        summary: Incident summary
        severity: Severity level
        location: Incident location
        actions: JSON string containing recommended actions
        
    Returns:
        Dictionary containing communication template
    """
    try:
        # Only create templates for HIGH and CRITICAL incidents
        if severity not in [SeverityLevel.HIGH.value, SeverityLevel.CRITICAL.value]:
            logger.info(f"Skipping template creation for {severity} severity incident")
            return {
                "success": True,
                "template_created": False,
                "reason": f"Templates only created for HIGH and CRITICAL incidents (severity: {severity})"
            }
        
        # Parse actions
        try:
            action_list = json.loads(actions) if isinstance(actions, str) else actions
        except json.JSONDecodeError:
            action_list = []
        
        # Generate timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        # Create template based on severity
        if severity == SeverityLevel.CRITICAL.value:
            template = f"""URGENT INCIDENT NOTIFICATION - CRITICAL SEVERITY

Incident ID: {incident_id}
Severity Level: CRITICAL
Date/Time: {timestamp}
Location: {location or "Multiple locations / To be determined"}

SITUATION SUMMARY:
{summary}

IMMEDIATE ACTIONS REQUIRED:
"""
            for i, action in enumerate(action_list[:5], 1):  # Top 5 actions
                template += f"\n{i}. {action.get('action', 'N/A')}"
                template += f"\n   Responsible: {action.get('responsible', 'N/A')}"
                template += f"\n   Timeline: {action.get('timeline', 'N/A')}\n"
            
            template += """
RESPONSE STATUS:
Emergency response protocols have been activated. All relevant personnel have been notified.
Incident command structure is being established.

NEXT UPDATE:
Updates will be provided every 30 minutes or as situation develops.

CONTACT INFORMATION:
Emergency Operations Center: [Contact Details]
Incident Commander: [Contact Details]

This is a CRITICAL incident requiring immediate attention and action.
"""
        
        else:  # HIGH
            template = f"""INCIDENT NOTIFICATION - HIGH SEVERITY

Incident ID: {incident_id}
Severity Level: HIGH
Date/Time: {timestamp}
Location: {location or "Multiple locations / To be determined"}

SITUATION SUMMARY:
{summary}

RECOMMENDED ACTIONS:
"""
            for i, action in enumerate(action_list[:4], 1):  # Top 4 actions
                template += f"\n{i}. {action.get('action', 'N/A')}"
                template += f"\n   Responsible: {action.get('responsible', 'N/A')}"
                template += f"\n   Timeline: {action.get('timeline', 'N/A')}\n"
            
            template += """
RESPONSE STATUS:
Response teams have been alerted and are preparing for deployment.
Situation is being monitored closely.

NEXT UPDATE:
Updates will be provided every 2 hours or as situation develops.

CONTACT INFORMATION:
Operations Center: [Contact Details]
Duty Officer: [Contact Details]

Please acknowledge receipt of this notification.
"""
        
        logger.info(f"Created communication template for incident {incident_id}")
        
        return {
            "success": True,
            "template_created": True,
            "template": template,
            "severity": severity
        }
    
    except Exception as e:
        logger.error(f"Error creating communication template: {e}")
        return {
            "success": False,
            "error": str(e),
            "template_created": False
        }


def persist_incident_tool(
    incident_data: str,
    db_path: str
) -> Dict[str, Any]:
    """
    Tool function to persist incident to SQLite database.
    
    Saves the complete incident record with all metadata to the database
    and updates the associated job status to COMPLETED.
    
    Args:
        incident_data: JSON string containing complete incident data
        db_path: Path to SQLite database
        
    Returns:
        Dictionary containing persistence result
    """
    try:
        # Parse incident data
        try:
            data = json.loads(incident_data) if isinstance(incident_data, str) else incident_data
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {e}"
            }
        
        # Extract required fields
        incident_id = data.get("incident_id")
        if not incident_id:
            return {
                "success": False,
                "error": "Missing incident_id"
            }
        
        summary = data.get("summary", "")
        severity = data.get("severity", "MEDIUM")
        priority_score = data.get("priority_score", 0.5)
        status = data.get("status", IncidentStatus.DISPATCHED.value)
        job_id = data.get("job_id")
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert or replace incident
        cursor.execute("""
            INSERT OR REPLACE INTO incidents 
            (incident_id, summary, severity, priority_score, status, created_at, updated_at, full_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            incident_id,
            summary,
            severity,
            priority_score,
            status,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            json.dumps(data)
        ))
        
        # Update job status to COMPLETED if job_id is provided
        if job_id:
            cursor.execute("""
                UPDATE jobs
                SET status = ?, updated_at = ?, result = ?
                WHERE job_id = ?
            """, (
                JobStatus.COMPLETED.value,
                datetime.utcnow().isoformat(),
                json.dumps({"incident_id": incident_id, "status": "dispatched"}),
                job_id
            ))
            
            job_updated = cursor.rowcount > 0
        else:
            job_updated = False
        
        conn.commit()
        conn.close()
        
        logger.info(f"Persisted incident {incident_id} to database (job updated: {job_updated})")
        
        return {
            "success": True,
            "incident_id": incident_id,
            "persisted_at": datetime.utcnow().isoformat(),
            "job_updated": job_updated,
            "job_id": job_id
        }
    
    except Exception as e:
        logger.error(f"Error persisting incident: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def notify_dashboard_tool(
    incident_data: str
) -> Dict[str, Any]:
    """
    Tool function to notify dashboard of new incident.
    
    Adds incident to in-memory cache for dashboard access and
    emits event for dashboard refresh.
    
    Args:
        incident_data: JSON string containing incident data
        
    Returns:
        Dictionary containing notification result
    """
    try:
        # Parse incident data
        try:
            data = json.loads(incident_data) if isinstance(incident_data, str) else incident_data
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {e}"
            }
        
        incident_id = data.get("incident_id")
        if not incident_id:
            return {
                "success": False,
                "error": "Missing incident_id"
            }
        
        # Add to cache
        INCIDENT_CACHE[incident_id] = {
            "incident_id": incident_id,
            "summary": data.get("summary", ""),
            "severity": data.get("severity", "MEDIUM"),
            "priority_score": data.get("priority_score", 0.5),
            "status": data.get("status", IncidentStatus.DISPATCHED.value),
            "recommended_actions": data.get("recommended_actions", []),
            "communication_template": data.get("communication_template", ""),
            "created_at": data.get("created_at", datetime.utcnow().isoformat()),
            "dispatched_at": data.get("dispatched_at", datetime.utcnow().isoformat()),
            "full_data": data
        }
        
        logger.info(f"Added incident {incident_id} to dashboard cache")
        
        return {
            "success": True,
            "incident_id": incident_id,
            "cache_size": len(INCIDENT_CACHE),
            "notified_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error notifying dashboard: {e}")
        return {
            "success": False,
            "error": str(e)
        }


class DispatcherAgent:
    """
    Dispatcher Agent for action generation and incident finalization.
    
    Responsibilities:
    - Generate recommended actions with specific steps and timelines
    - Create communication templates for HIGH and CRITICAL incidents
    - Persist complete incident data to database
    - Update job status to COMPLETED
    - Notify dashboard of new incidents
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-lite",
        db_path: str = "./capstone/data/agentfleet.db"
    ):
        """
        Initialize the Dispatcher Agent.
        
        Args:
            model_name: Name of the Gemini model to use
            db_path: Path to SQLite database
        """
        self.model_name = model_name
        self.agent_name = "dispatcher_agent"
        self.db_path = db_path
        
        # Initialize Gemini client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        
        # Agent instruction
        self.instruction = """You are the Dispatcher Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive triaged incidents from the Triage Agent via A2A protocol
2. Generate recommended actions with specific steps, responsible parties, and timelines
3. Create communication templates for HIGH and CRITICAL severity incidents
4. Persist complete incident data to the database
5. Update job status to COMPLETED
6. Notify the Operator Dashboard of new incidents

Action Generation Guidelines:
- Provide specific, actionable recommendations
- Assign clear responsible parties
- Include realistic timelines based on severity
- Prioritize human safety and infrastructure protection
- Scale response appropriately to severity level

Communication Template Guidelines:
- Use professional, clear language
- Include all critical information (ID, severity, location, summary)
- List top priority actions
- Provide contact information placeholders
- Set expectations for next updates

When processing incidents:
- Use the generate_actions tool to create recommended actions
- Use the create_communication_template tool for HIGH/CRITICAL incidents
- Use the persist_incident tool to save to database
- Use the notify_dashboard tool to make incident available to operators
- Always ensure complete data persistence
- Confirm job status is updated to COMPLETED

Be thorough and professional in all communications.
Ensure operators have all information needed to respond effectively.
"""
        
        # Define tools
        self.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="generate_actions",
                        description="Generate recommended actions for incident response with specific steps, responsible parties, and timelines",
                        parameters={
                            "type": "object",
                            "properties": {
                                "incident_id": {
                                    "type": "string",
                                    "description": "Unique incident identifier"
                                },
                                "summary": {
                                    "type": "string",
                                    "description": "Incident summary"
                                },
                                "severity": {
                                    "type": "string",
                                    "description": "Severity level (LOW/MEDIUM/HIGH/CRITICAL)"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "Incident location"
                                },
                                "key_facts": {
                                    "type": "string",
                                    "description": "JSON string containing key facts"
                                }
                            },
                            "required": ["incident_id", "summary", "severity"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="create_communication_template",
                        description="Create communication template for stakeholder notification (HIGH and CRITICAL incidents only)",
                        parameters={
                            "type": "object",
                            "properties": {
                                "incident_id": {
                                    "type": "string",
                                    "description": "Unique incident identifier"
                                },
                                "summary": {
                                    "type": "string",
                                    "description": "Incident summary"
                                },
                                "severity": {
                                    "type": "string",
                                    "description": "Severity level"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "Incident location"
                                },
                                "actions": {
                                    "type": "string",
                                    "description": "JSON string containing recommended actions"
                                }
                            },
                            "required": ["incident_id", "summary", "severity"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="persist_incident",
                        description="Persist complete incident data to SQLite database and update job status to COMPLETED",
                        parameters={
                            "type": "object",
                            "properties": {
                                "incident_data": {
                                    "type": "string",
                                    "description": "JSON string containing complete incident data"
                                },
                                "db_path": {
                                    "type": "string",
                                    "description": "Path to SQLite database"
                                }
                            },
                            "required": ["incident_data", "db_path"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="notify_dashboard",
                        description="Notify dashboard of new incident by adding to cache",
                        parameters={
                            "type": "object",
                            "properties": {
                                "incident_data": {
                                    "type": "string",
                                    "description": "JSON string containing incident data"
                                }
                            },
                            "required": ["incident_data"]
                        }
                    )
                ]
            )
        ]
        
        logger.info(f"Initialized Dispatcher Agent with model {model_name}")
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool function."""
        if tool_name == "generate_actions":
            return generate_actions_tool(**tool_args)
        elif tool_name == "create_communication_template":
            return create_communication_template_tool(**tool_args)
        elif tool_name == "persist_incident":
            return persist_incident_tool(**tool_args)
        elif tool_name == "notify_dashboard":
            return notify_dashboard_tool(**tool_args)
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
    
    def process_triage_envelope(self, envelope_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a triaged incident envelope from the Triage Agent.
        
        Args:
            envelope_data: MCP envelope containing triaged incident
            
        Returns:
            Processing result with dispatched incident
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
            
            # Extract triage data
            triage_data = envelope.payload.get("data", {})
            incident_id = triage_data.get("incident_id", "unknown")
            severity = triage_data.get("severity", "MEDIUM")
            priority_score = triage_data.get("priority_score", 0.5)
            job_id = triage_data.get("job_id", "")
            
            # Extract incident brief from triage data
            brief_data = triage_data.get("brief", {})
            summary = brief_data.get("summary", "")
            location = brief_data.get("location", "")
            key_facts = brief_data.get("key_facts", [])
            
            # Create processing message
            message = f"""Process this triaged incident for dispatch:

Incident ID: {incident_id}
Severity: {severity}
Priority Score: {priority_score}
Job ID: {job_id}
Summary: {summary}
Location: {location}
Key Facts: {json.dumps(key_facts)}

Full Triage Data: {json.dumps(triage_data)}

Tasks:
1. Generate recommended actions with specific steps, responsible parties, and timelines
2. Create communication template if severity is HIGH or CRITICAL
3. Persist complete incident data to database
4. Update job status to COMPLETED
5. Notify dashboard

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
            logger.error(f"Error processing triage envelope: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def create_dispatcher_agent(
    model_name: str = "gemini-2.0-flash-lite",
    db_path: str = "./capstone/data/agentfleet.db"
) -> DispatcherAgent:
    """
    Factory function to create a Dispatcher Agent instance.
    
    Args:
        model_name: Name of the Gemini model to use
        db_path: Path to SQLite database
        
    Returns:
        DispatcherAgent instance
    """
    return DispatcherAgent(
        model_name=model_name,
        db_path=db_path
    )


def get_incident_cache() -> Dict[str, Dict[str, Any]]:
    """
    Get the incident cache for dashboard access.
    
    Returns:
        Dictionary of incidents keyed by incident_id
    """
    return INCIDENT_CACHE
