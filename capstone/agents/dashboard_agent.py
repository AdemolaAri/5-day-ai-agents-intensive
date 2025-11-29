import json
import logging
from typing import Any, Dict
from datetime import datetime

from capstone.agents.dispatcher_agent import get_incident_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_dashboard_markdown_tool() -> Dict[str, Any]:
    """
    Tool function to create a markdown dashboard from incident cache.
    
    Creates a formatted markdown table displaying all relevant incident information
    from the INCIDENT_CACHE for the operator dashboard.
    
    Returns:
        Dictionary containing the markdown dashboard
    """
    try:
        # Get incidents from cache
        incident_cache = get_incident_cache()
        
        if not incident_cache:
            markdown = """# 🚨 Incident Response Dashboard

**Last Updated:** """ + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC") + """

## Current Incidents

No incidents currently in the system.

## Incident Summary

- **Total Incidents:** 0
- **Critical:** 0
- **High:** 0
- **Medium:** 0
- **Low:** 0

No action items required at this time.
"""
            logger.info("Created dashboard with no incidents")
            
            return {
                "success": True,
                "dashboard_markdown": markdown,
                "incident_count": 0,
                "cache_size": 0
            }
        
        # Count incidents by severity
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        # Create markdown table header
        markdown = f"""# 🚨 Incident Response Dashboard

**Last Updated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

## Current Incidents

| Incident ID | Severity | Status | Priority | Location | Summary | Actions | Dispatched At |
|-------------|----------|--------|----------|----------|---------|---------|---------------|
"""
        
        # Sort incidents by severity and priority score
        sorted_incidents = []
        for incident_id, incident_data in incident_cache.items():
            severity = incident_data.get("severity", "UNKNOWN")
            priority_score = incident_data.get("priority_score", 0.0)
            sorted_incidents.append((incident_id, incident_data, severity, priority_score))
        
        # Sort by severity (CRITICAL, HIGH, MEDIUM, LOW) then by priority score (high to low)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_incidents.sort(key=lambda x: (severity_order.get(x[2], 4), -x[3]))
        
        # Add incidents to table
        for incident_id, incident_data in [(item[0], item[1]) for item in sorted_incidents]:
            summary = incident_data.get("summary", "No summary available")
            severity = incident_data.get("severity", "UNKNOWN")
            priority_score = incident_data.get("priority_score", 0.0)
            status = incident_data.get("status", "DISPATCHED")
            location = incident_data.get("location", "N/A")
            dispatched_at = incident_data.get("dispatched_at", "N/A")
            recommended_actions = incident_data.get("recommended_actions", [])
            
            # Increment severity count
            if severity in severity_counts:
                severity_counts[severity] += 1
            
            # Format summary for display (limit to 50 characters)
            display_summary = summary[:47] + "..." if len(summary) > 50 else summary
            
            # Format timestamp
            if dispatched_at != "N/A":
                try:
                    # Convert ISO format to readable format
                    dt = datetime.fromisoformat(dispatched_at.replace('Z', '+00:00'))
                    dispatched_at = dt.strftime("%Y-%m-%d %H:%M UTC")
                except:
                    pass
            
            markdown += f"| {incident_id} | {severity} | {status} | {priority_score:.2f} | {location} | {display_summary} | {len(recommended_actions)} | {dispatched_at} |\n"
        
        # Add incident summary
        markdown += f"""

## Incident Summary

- **Total Incidents:** {len(incident_cache)}
- **Critical:** {severity_counts['CRITICAL']}
- **High:** {severity_counts['HIGH']}
- **Medium:** {severity_counts['MEDIUM']}
- **Low:** {severity_counts['LOW']}

"""
        
        # Add detailed action items for critical and high severity incidents
        critical_high_incidents = [
            (incident_id, incident_data) 
            for incident_id, incident_data in [(item[0], item[1]) for item in sorted_incidents]
            if incident_data.get("severity") in ["CRITICAL", "HIGH"]
        ]
        
        if critical_high_incidents:
            markdown += "## Critical & High Priority Action Items\n\n"
            
            for incident_id, incident_data in critical_high_incidents:
                severity = incident_data.get("severity", "UNKNOWN")
                summary = incident_data.get("summary", "No summary available")
                recommended_actions = incident_data.get("recommended_actions", [])
                
                markdown += f"### Incident {incident_id} ({severity})\n"
                markdown += f"**Summary:** {summary}\n\n"
                
                if recommended_actions:
                    markdown += "**Recommended Actions:**\n\n"
                    for i, action in enumerate(recommended_actions, 1):
                        action_text = action.get('action', 'N/A')
                        responsible = action.get('responsible', 'N/A')
                        timeline = action.get('timeline', 'N/A')
                        markdown += f"{i}. **{action_text}**\n"
                        markdown += f"   - **Responsible:** {responsible}\n"
                        markdown += f"   - **Timeline:** {timeline}\n\n"
                else:
                    markdown += "**Recommended Actions:** No specific actions recommended.\n\n"
                
                # Add communication template if available
                if incident_data.get("communication_template"):
                    markdown += "**Communication Template:**\n"
                    markdown += "```\n"
                    template = incident_data["communication_template"]
                    markdown += template[:300]  # Truncate long templates
                    if len(template) > 300:
                        markdown += "...\n[Template truncated - see full template in database]\n"
                    markdown += "\n```\n\n"
                
                markdown += "---\n\n"
        else:
            markdown += "## Action Items\n\nNo critical or high priority incidents requiring immediate action.\n\n"
        
        logger.info(f"Created dashboard markdown for {len(incident_cache)} incidents")
        
        return {
            "success": True,
            "dashboard_markdown": markdown,
            "incident_count": len(incident_cache),
            "cache_size": len(incident_cache),
            "severity_counts": severity_counts
        }
    
    except Exception as e:
        logger.error(f"Error creating dashboard markdown: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_dashboard_standalone():
    """
    Standalone test function to demonstrate dashboard functionality.
    This creates sample data directly without importing the dispatcher cache.
    """
    # Mock the get_incident_cache function for testing
    def mock_get_incident_cache():
        return {
            "INC-001": {
                "incident_id": "INC-001",
                "summary": "Major power outage affecting downtown area with 500+ residents without electricity",
                "severity": "CRITICAL",
                "priority_score": 0.95,
                "status": "DISPATCHED",
                "location": "Downtown District",
                "dispatched_at": "2023-11-28T14:30:00",
                "recommended_actions": [
                    {
                        "action": "Activate emergency response team immediately",
                        "responsible": "Emergency Operations Center",
                        "timeline": "Immediate (0-15 minutes)"
                    },
                    {
                        "action": "Deploy first responders to affected location",
                        "responsible": "Emergency Services Coordinator",
                        "timeline": "Within 15-30 minutes"
                    }
                ],
                "communication_template": "URGENT INCIDENT NOTIFICATION - CRITICAL SEVERITY...",
                "created_at": "2023-11-28T14:25:00",
                "full_data": {}
            },
            "INC-002": {
                "incident_id": "INC-002",
                "summary": "Minor water main break affecting local neighborhood",
                "severity": "MEDIUM",
                "priority_score": 0.65,
                "status": "DISPATCHED",
                "location": "Maple Street Area",
                "dispatched_at": "2023-11-28T13:45:00",
                "recommended_actions": [
                    {
                        "action": "Monitor situation for escalation",
                        "responsible": "Operations Center",
                        "timeline": "Continuous monitoring"
                    }
                ],
                "created_at": "2023-11-28T13:40:00",
                "full_data": {}
            }
        }
    
    # Temporarily replace the get_incident_cache function
    original_func = get_incident_cache
    globals()['get_incident_cache'] = mock_get_incident_cache
    
    try:
        # Generate dashboard
        result = create_dashboard_markdown_tool()
        
        if result["success"]:
            print("✅ Dashboard generated successfully!")
            print(f"   Incidents in dashboard: {result['incident_count']}")
            print(f"   Severity breakdown: {result['severity_counts']}")
            print("\n" + "="*50)
            print("DASHBOARD OUTPUT:")
            print("="*50)
            print(result["dashboard_markdown"])
        else:
            print(f"❌ Error generating dashboard: {result['error']}")
            
    finally:
        # Restore original function
        globals()['get_incident_cache'] = original_func


if __name__ == "__main__":
    # Run test if file is executed directly
    test_dashboard_standalone()
