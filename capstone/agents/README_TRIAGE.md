# Triage Agent

## Overview

The Triage Agent is a specialist agent in the AgentFleet incident response system responsible for severity classification, priority scoring, and job queue management. It receives incident briefs from the Summarizer Agent, analyzes them to determine severity levels, creates job queue entries for high-priority incidents, and forwards triaged incidents to the Dispatcher Agent.

## Responsibilities

1. **Severity Classification**: Analyze incident content and classify as LOW, MEDIUM, HIGH, or CRITICAL
2. **Priority Scoring**: Calculate priority scores (0.0 to 1.0) for incident ordering
3. **Job Queue Management**: Create and manage job entries in SQLite database
4. **A2A Communication**: Receive incidents from Summarizer Agent and forward to Dispatcher Agent
5. **Reasoning**: Provide clear explanations for severity assignments

## Severity Classification Guidelines

### CRITICAL (Priority Score: 0.7 - 1.0)
- Immediate threat to life
- Major infrastructure failure
- Widespread impact (>1000 people affected)
- Multiple fatalities
- Catastrophic damage

**Examples**: Major flooding with evacuations, building collapse, mass casualty event

### HIGH (Priority Score: 0.5 - 0.7)
- Significant threat to safety
- Infrastructure damage
- Regional impact (100-1000 people affected)
- Casualties reported
- Severe damage

**Examples**: Fire with injuries, regional power outage, hazardous material spill

### MEDIUM (Priority Score: 0.3 - 0.5)
- Moderate threat
- Localized damage
- Limited impact (10-100 people affected)
- Minor injuries possible
- Moderate damage

**Examples**: Traffic accident, small fire, localized flooding

### LOW (Priority Score: 0.1 - 0.3)
- Minor threat
- Minimal damage
- Very limited impact (<10 people affected)
- No injuries
- Minimal damage

**Examples**: Minor traffic disruption, small utility outage, weather advisory

## Tools

### classify_severity
Analyzes incident content and assigns severity level with priority score.

**Parameters**:
- `summary` (string): Incident summary text
- `key_facts` (string): JSON string containing key facts
- `location` (string, optional): Incident location
- `reliability_score` (number, optional): Verification reliability score

**Returns**:
- `severity`: Severity level (LOW/MEDIUM/HIGH/CRITICAL)
- `priority_score`: Priority score (0.0 to 1.0)
- `reasoning`: Explanation for severity assignment

### create_job
Creates a job queue entry for HIGH and CRITICAL incidents.

**Parameters**:
- `incident_id` (string): Unique incident identifier
- `severity` (string): Severity level
- `priority_score` (number): Priority score
- `db_path` (string): Path to SQLite database

**Returns**:
- `job_id`: Unique job identifier (if created)
- `job_created`: Boolean indicating if job was created
- `status`: Job status (PENDING)

### update_job_status
Updates the status of an existing job.

**Parameters**:
- `job_id` (string): Job identifier
- `status` (string): New status (PENDING/PROCESSING/COMPLETED/FAILED)
- `result` (string, optional): Result data as JSON string
- `db_path` (string): Path to SQLite database

**Returns**:
- `success`: Boolean indicating success
- `updated_at`: Update timestamp

### query_jobs
Queries jobs from the database with optional filters.

**Parameters**:
- `status` (string, optional): Status filter
- `incident_id` (string, optional): Incident ID filter
- `limit` (integer, optional): Maximum number of results (default: 100)
- `db_path` (string): Path to SQLite database

**Returns**:
- `jobs`: List of job objects
- `count`: Number of jobs returned

### forward_to_dispatcher
Forwards triaged incident envelope to the Dispatcher Agent via A2A protocol.

**Parameters**:
- `envelope_json` (string): JSON string containing MCP envelope

**Returns**:
- `success`: Boolean indicating success
- `response`: Response from Dispatcher Agent
- `attempts`: Number of retry attempts made

## A2A Protocol

### Endpoints

- **Agent Card**: `GET /.well-known/agent-card.json`
- **Tasks**: `POST /tasks`
- **Health**: `GET /health`

### Input Schema

Expects MCP envelopes with schema `incident_brief_v1`:

```json
{
  "schema": "incident_brief_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "summarizer_agent",
  "payload": {
    "type": "incident",
    "data": {
      "incident_id": "uuid",
      "summary": "string (max 200 words)",
      "key_facts": ["fact1", "fact2"],
      "location": "string",
      "affected_entities": ["entity1"],
      "similar_incidents": []
    }
  }
}
```

### Output Schema

Returns MCP envelopes with schema `triaged_incident_v1`:

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
      "severity": "HIGH",
      "priority_score": 0.85,
      "job_id": "uuid",
      "reasoning": "string",
      "triaged_at": "ISO8601"
    }
  }
}
```

## Job Queue

The Triage Agent manages a persistent job queue in SQLite for tracking HIGH and CRITICAL incidents.

### Job Lifecycle

1. **PENDING**: Job created, awaiting processing
2. **PROCESSING**: Job is being processed
3. **COMPLETED**: Job completed successfully
4. **FAILED**: Job failed with error

### Database Schema

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    result JSON
);

CREATE INDEX idx_jobs_status ON jobs(status);
```

## Configuration

### Environment Variables

- `GOOGLE_API_KEY`: Gemini API key (required)
- `DISPATCHER_AGENT_URL`: URL of Dispatcher Agent (default: http://localhost:8005)
- `DATABASE_PATH`: Path to SQLite database (default: ./capstone/data/agentfleet.db)
- `TRIAGE_HOST`: Server host (default: 0.0.0.0)
- `TRIAGE_PORT`: Server port (default: 8004)

## Running the Agent

### Start Server

```bash
# Using default configuration
python capstone/agents/triage_server.py

# Using custom configuration
TRIAGE_PORT=9004 DATABASE_PATH=/path/to/db.sqlite python capstone/agents/triage_server.py
```

### Health Check

```bash
curl http://localhost:8004/health
```

### Agent Card

```bash
curl http://localhost:8004/.well-known/agent-card.json
```

## Error Handling

### A2A Communication Errors

The agent implements exponential backoff retry logic for A2A communication:
- Max retries: 3
- Initial delay: 1.0 seconds
- Backoff multiplier: 2.0
- Max delay: 10.0 seconds

### Database Errors

Database operations include error handling and logging. Failed operations return error responses without crashing the agent.

### Tool Errors

Tool execution errors are caught and returned as error responses with detailed error messages.

## Logging

The agent logs all operations including:
- Incident processing
- Severity classification
- Job creation and updates
- A2A communication
- Tool execution
- Errors and warnings

Log level can be configured via Python logging configuration.

## Requirements Satisfied

- **4.1**: Analyze incident content to determine severity level
- **4.2**: Classify incidents as LOW, MEDIUM, HIGH, or CRITICAL
- **4.3**: Create priority job entries for CRITICAL and HIGH incidents
- **4.4**: Assign unique job identifier and timestamp
- **4.5**: Forward triaged incident to Dispatcher Agent via A2A protocol
- **6.1**: Expose agent via A2A protocol
- **6.2**: Generate agent card at /.well-known/agent-card.json
- **6.3**: Validate envelope schema before processing
- **6.4**: Return A2A response envelope with status and result
- **6.5**: Retry A2A requests with exponential backoff
- **11.2**: Persist jobs to SQLite database
- **11.3**: Update job status with completion timestamp

## Integration

The Triage Agent integrates with:
- **Summarizer Agent** (upstream): Receives incident briefs
- **Dispatcher Agent** (downstream): Forwards triaged incidents
- **SQLite Database**: Persists job queue entries
- **Memory Bank**: Indirectly via incident data

## Testing

See `capstone/tests/test_triage_agent.py` for unit and integration tests.

## Future Enhancements

- Machine learning-based severity classification
- Dynamic severity thresholds based on historical data
- Advanced job queue prioritization algorithms
- Real-time job queue monitoring dashboard
- Automated job retry mechanisms
