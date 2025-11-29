
import logging
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any

from capstone.models import (
    IncidentStatus,
    SeverityLevel,
    JobStatus
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

def get_incident_cache() -> Dict[str, Dict[str, Any]]:
    """
    Get the incident cache for dashboard access.
    
    Returns:
        Dictionary of incidents keyed by incident_id
    """
    return INCIDENT_CACHE
