# Dispatcher Agent

## Overview

The Dispatcher Agent is the final agent in the AgentFleet incident response pipeline. It receives triaged incidents from the Triage Agent, generates actionable recommendations, creates communication templates, persists complete incident data to the database, and notifies the operator dashboard.

## Responsibilities

1. **Action Generation**: Create specific, actionable recommendations with:
   - Clear action descriptions
   - Responsible parties
   - Expected timelines
   - Severity-appropriate response levels

2. **Communication Templates**: Generate professional stakeholder notification templates for HIGH and CRITICAL incidents

3. **Incident Persistence**: Save complete incident records to SQLite database with full metadata

4. **Job Status Management**: Update job queue entries to COMPLETED status

5. **Dashboard Notification**: Add incidents to in-memory cache for operator dashboard access

## Architecture

### Agent Configuration

- **Model**: `gemini-2.0-flash-lite` (fast, cost-effective)
- **Port**: 8005 (A2A protocol)
- **Tools**: 
  - `generate_actions`: Generate recommended actions
  - `create_communication_template`: Create stakeholder notifications
  - `persist_incident`: Save to database
  - `notify_dashboard`: Add to dashboard cache

### Input

Receives MCP envelopes with schema `triaged_incident_v1` containing:
```json
{
  "schema": "triaged_incident_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "triage_agent",
  "payload": {
    "type": "triage",
    "data": {
      "incident_id": "uuid",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "priority_score": 0.85,
      "job_id": "uuid",
      "reasoning": "string",
      "brief": {
        "incident_id": "uuid",
        "summary": "string",
        "key_facts": ["fact1", "fact2"],
        "location": "string",
        "affected_entities": ["entity1"]
      }
    }
  }
}
```

### Output

Returns MCP envelopes with schema `dispatch_v1` containing:
```json
{
  "schema": "dispatch_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "dispatcher_agent",
  "payload": {
    "type": "dispatch",
    "data": {
      "incident_id": "uuid",
      "recommended_actions": [
        {
          "action": "string",
          "responsible": "string",
          "timeline": "string"
        }
      ],
      "communication_template": "string",
      "status": "DISPATCHED",
      "dispatched_at": "ISO8601"
    }
  }
}
```

## Action Generation Logic

Actions are generated based on severity level:

### CRITICAL Severity
- Activate emergency response team immediately (0-15 minutes)
- Establish incident command post (within 30 minutes)
- Deploy first responders (15-30 minutes)
- Initiate evacuation procedures if necessary (30-60 minutes)
- Notify senior leadership and government agencies (within 15 minutes)

### HIGH Severity
- Alert emergency response team and place on standby (within 30 minutes)
- Dispatch assessment team (within 1 hour)
- Coordinate with local authorities (within 1 hour)
- Prepare resources for deployment (within 2 hours)

### MEDIUM Severity
- Monitor situation for escalation (continuous)
- Conduct preliminary assessment (2-4 hours)
- Notify relevant stakeholders (within 4 hours)

### LOW Severity
- Log incident for record keeping (within 24 hours)
- Review and update procedures if needed (within 1 week)

## Communication Templates

Templates are automatically generated for HIGH and CRITICAL incidents with:

- **CRITICAL Template**:
  - "URGENT INCIDENT NOTIFICATION" header
  - Situation summary
  - Top 5 immediate actions required
  - Response status
  - Update frequency: every 30 minutes
  - Emergency contact information

- **HIGH Template**:
  - "INCIDENT NOTIFICATION" header
  - Situation summary
  - Top 4 recommended actions
  - Response status
  - Update frequency: every 2 hours
  - Operations contact information

## Database Persistence

Incidents are saved to the `incidents` table with:
- `incident_id` (PRIMARY KEY)
- `summary` (TEXT)
- `severity` (TEXT)
- `priority_score` (REAL)
- `status` (TEXT)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)
- `full_data` (JSON) - Complete incident data

Associated jobs are updated to `COMPLETED` status in the `jobs` table.

## Dashboard Cache

Incidents are added to an in-memory cache (`INCIDENT_CACHE`) for fast dashboard access:
```python
{
  "incident_id": {
    "incident_id": "uuid",
    "summary": "string",
    "severity": "HIGH",
    "priority_score": 0.85,
    "status": "DISPATCHED",
    "recommended_actions": [...],
    "communication_template": "string",
    "created_at": "ISO8601",
    "dispatched_at": "ISO8601",
    "full_data": {...}
  }
}
```

## API Endpoints

### Agent Card
```
GET /.well-known/agent-card.json
```
Returns agent capabilities and schema information.

### Task Processing
```
POST /tasks
Content-Type: application/json

{
  "schema": "triaged_incident_v1",
  "session_id": "uuid",
  "payload": {...}
}
```

### Health Check
```
GET /health
```
Returns agent health status and cache statistics.

### Incidents List
```
GET /incidents
```
Returns all incidents from cache, sorted by priority.

### Specific Incident
```
GET /incidents/{incident_id}
```
Returns details for a specific incident.

## Usage

### Starting the Server

```bash
# Set environment variables
export GOOGLE_API_KEY="your-api-key"
export DATABASE_PATH="./capstone/data/agentfleet.db"
export DISPATCHER_HOST="0.0.0.0"
export DISPATCHER_PORT="8005"

# Start the server
python -m capstone.agents.dispatcher_server
```

### Programmatic Usage

```python
from capstone.agents.dispatcher_agent import create_dispatcher_agent

# Create agent
agent = create_dispatcher_agent(
    model_name="gemini-2.0-flash-lite",
    db_path="./capstone/data/agentfleet.db"
)

# Process triage envelope
result = agent.process_triage_envelope(envelope_data)

if result["success"]:
    print(f"Dispatched incident: {result['incident_id']}")
```

### A2A Communication

```python
import httpx

# Forward triaged incident to Dispatcher
response = httpx.post(
    "http://localhost:8005/tasks",
    json=triage_envelope,
    headers={"Content-Type": "application/json"}
)

if response.status_code == 200:
    result = response.json()
    print(f"Dispatch successful: {result['incident_id']}")
```

## Error Handling

The agent implements comprehensive error handling:

1. **Envelope Validation**: Invalid envelopes return 400 Bad Request
2. **Tool Failures**: Gracefully handled with error logging
3. **Database Errors**: Transaction rollback and error reporting
4. **Missing Data**: Default values and clear error messages

## Logging

All operations are logged with structured information:
- Tool invocations with parameters
- Database operations
- Cache updates
- Error conditions with full context

## Testing

Run the agent tests:
```bash
# Unit tests for tools
python -m pytest capstone/tests/test_dispatcher_agent.py

# Integration tests
python -m pytest capstone/tests/test_dispatcher_integration.py
```

## Requirements Satisfied

- **5.1**: Generate list of recommended actions
- **5.2**: Include specific steps, responsible parties, and timelines
- **5.3**: Generate communication templates for HIGH/CRITICAL incidents
- **5.4**: Persist incident record with all metadata to database
- **5.5**: Make incident available to Operator Dashboard
- **6.1**: Expose agent via A2A protocol
- **6.2**: Generate agent card at /.well-known/agent-card.json
- **11.3**: Update job status with completion timestamp
- **11.5**: Implement full incident data serialization

## Next Steps

After the Dispatcher Agent completes processing:
1. Incident is persisted to database
2. Job status is updated to COMPLETED
3. Incident appears in dashboard cache
4. Operators can view and acknowledge the incident
5. Communication templates can be sent to stakeholders

## Related Agents

- **Upstream**: Triage Agent (port 8004)
- **Downstream**: Operator Dashboard (Jupyter notebook)
- **Database**: SQLite at `./capstone/data/agentfleet.db`
