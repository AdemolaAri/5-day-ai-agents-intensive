# AgentFleet - Multi-Agent Incident Response System

A production-style multi-agent incident response system built with Google's Agent Development Kit (ADK).

## Project Structure

```
capstone/
├── agents/          # Agent implementations (Ingest, Verifier, Summarizer, Triage, Dispatcher)
├── tools/           # Custom tools for agents (stream connectors, verification, etc.)
├── data/            # Database and data storage
│   ├── init_db.py   # Database initialization script
│   └── agentfleet.db # SQLite database
├── notebooks/       # Jupyter notebooks for dashboard and demos
├── requirements.txt # Python dependencies
├── .env.example     # Environment configuration template
└── README.md        # This file
```

## Setup

1. **Create virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your GOOGLE_API_KEY
   ```

4. **Initialize database** (already done during setup):
   ```bash
   python data/init_db.py
   ```

## Architecture

AgentFleet consists of 5 specialist agents communicating via A2A protocol:

1. **Ingest Agent** (port 8001) - Event stream ingestion and normalization
2. **Verifier Agent** (port 8002) - Fact-checking and source reliability scoring
3. **Summarizer Agent** (port 8003) - Incident brief generation with memory
4. **Triage Agent** (port 8004) - Severity classification and job queue management
5. **Dispatcher Agent** (port 8005) - Action generation and incident persistence

## Database Schema

### Jobs Table
- `job_id` (TEXT, PRIMARY KEY)
- `incident_id` (TEXT)
- `status` (TEXT) - PENDING, PROCESSING, COMPLETED, FAILED
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)
- `result` (JSON)

### Incidents Table
- `incident_id` (TEXT, PRIMARY KEY)
- `summary` (TEXT)
- `severity` (TEXT) - LOW, MEDIUM, HIGH, CRITICAL
- `priority_score` (REAL)
- `status` (TEXT)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)
- `full_data` (JSON)

## Next Steps

Follow the implementation plan in `.kiro/specs/agent-fleet/tasks.md` to build the agents and tools.

## Requirements

See `.kiro/specs/agent-fleet/requirements.md` for detailed system requirements.

## Design

See `.kiro/specs/agent-fleet/design.md` for architecture and design decisions.
