
import uuid
import logging
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from capstone.models import (
    SeverityLevel,
    Job,
    JobStatus
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
