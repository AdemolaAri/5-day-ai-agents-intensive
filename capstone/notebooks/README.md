# 911 AgentFleet: Multi-Agent Emergency Response System
## Agents for Good — A Comprehensive Demonstration

Welcome to the AgentFleet demonstration! This capstone project showcases a **multi-agent system designed to save lives and protect communities** through intelligent emergency response and incident management using Google's Agent Development Kit (ADK).

### Why This Matters: Agents for Good

AgentFleet represents how AI agents can benefit entire communities by:
- **Reducing Response Time**: Automating incident triage and dispatch coordination
- **Improving Accuracy**: Verifying claims and assessing reliability across multiple sources
- **Saving Lives**: Prioritizing critical incidents for faster emergency response
- **Supporting First Responders**: Handling data processing so human operators can focus on action

This demo is a **proof-of-concept for what's possible**—imagine scaling this to coordinate emergency response across cities, regions, or entire nations.

### Project Overview

AgentFleet is an advanced multi-agent system that processes emergency events through a sophisticated pipeline of specialized AI agents:

1. **Ingest Agent** - Normalizes raw event data from various sources (social media, sensors, emergency feeds)
2. **Verifier Agent** - Verifies claims and assesses source reliability to reduce false alarms
3. **Summarizer Agent** - Creates concise incident summaries with historical context for operators
4. **Triage Agent** - Classifies incident severity (LOW, MEDIUM, HIGH, CRITICAL) for prioritization
5. **Dispatcher Agent** - Generates actionable recommendations and communicates with response teams
6. **Dashboard Agent** - Creates markdown dashboards for human operators to visualize and manage emergency response operations

## 2. Ingest Agent Setup

The Ingest Agent is the first component in the AgentFleet pipeline. It connects to multiple event sources, normalizes incoming data, and prepares events for downstream agents.

### 2.1 Starting the Ingest Agent A2A Server

We launch the Ingest Agent as a background service using **Uvicorn**, an ASGI application server. This makes the agent accessible via HTTP as an Agent-to-Agent (A2A) service:

- **Service Type**: Python application running on localhost
- **Port**: 8001
- **Protocol**: HTTP REST with well-known agent card discovery
- **Module**: `capstone.agents.ingest_agent:app`

## 3. Verifier Agent Setup

The Verifier Agent is the second component in the AgentFleet pipeline. It receives normalized events from the Ingest Agent and validates claims by fact-checking them against reliable sources, then scores the overall reliability of each event.

### 3.1 Import Verifier Tools

We begin by importing the specialized tools that the Verifier Agent uses to perform its verification tasks:

The tools include:
- **Fact-Checking Tool**: Cross-references claims with trusted databases and news sources
- **Source Reliability Assessor**: Evaluates the credibility of information sources based on historical accuracy

## 4. Summarizer Agent Setup

The Summarizer Agent is the third component in the AgentFleet pipeline. It receives verified events from the Verifier Agent and transforms them into concise, actionable incident briefs for human operators.

### 4.1 Import Summarizer Tools

We begin by importing the specialized tool that the Summarizer Agent uses to extract and structure key information:

The Summarizer Agent performs the following functions:

- **Receives verified events** with reliability scores from the Verifier Agent
- **Generates concise incident briefs** (maximum 200 words) suitable for rapid operator review
- **Extracts key facts** including location, time, affected entities, and impact assessment
- **Structures output** with organized information for downstream agents (Triage and Dispatcher)
- **Explains reasoning** about which facts were included and why they're important

The summarizer uses the `extract_key_facts_tool` to identify and organize critical information from verified claims, ensuring that operators receive clear, focused summaries that enable faster decision-making in emergency response scenarios.

## 5. Triage Agent Setup

The Triage Agent is the fourth component in the AgentFleet pipeline. It receives incident briefs from the Summarizer Agent and classifies them by severity level to prioritize emergency response.

### 5.1 Import Triage Tools

We begin by importing the specialized tools that the Triage Agent uses to classify incidents and manage the response queue:

The Triage Agent performs the following functions:

- **Receives incident briefs** from the Summarizer Agent with key facts and summaries
- **Analyzes incident content** to determine the appropriate severity classification
- **Classifies incidents** into four levels: LOW, MEDIUM, HIGH, or CRITICAL
- **Calculates priority scores** (0.0 to 1.0) for incident ordering and dispatch sequencing
- **Creates job queue entries** for HIGH and CRITICAL incidents to alert response teams
- **Forwards triaged incidents** to the Dispatcher Agent for action generation

**Severity Classification Guidelines:**
- **CRITICAL**: Immediate threat to life, major infrastructure failure, widespread impact (>1000 affected)
- **HIGH**: Significant threat, infrastructure damage, regional impact (100–1000 affected)
- **MEDIUM**: Moderate threat, localized damage, limited impact (10–100 affected)
- **LOW**: Minor threat, minimal damage, very limited impact (<10 affected)

**Key Capabilities:**
- Intelligent severity analysis based on multiple factors (threat level, scope, casualties)
- Priority scoring for efficient incident sequencing
- Job queue creation for automated escalation
- Reasoning transparency for operator review and audit trails

This agent serves as the critical decision point in the pipeline, ensuring that limited emergency resources are deployed to the most urgent incidents first, ultimately saving lives through intelligent prioritization.

## 6. Dispatcher Agent Setup

The Dispatcher Agent is the fifth and final component in the AgentFleet pipeline. It receives triaged incidents from the Triage Agent and converts them into concrete action plans, communication templates, and persistent records for emergency response teams.

### 6.1 Import Dispatcher Tools

We begin by importing the specialized tools that the Dispatcher Agent uses to generate actions, create communications, and persist incident data:

The Dispatcher Agent performs the following functions:

- **Receives triaged incidents** from the Triage Agent with severity classifications and priority scores
- **Generates recommended actions** with specific steps, responsible parties, and realistic timelines
- **Creates communication templates** for HIGH and CRITICAL severity incidents to alert response teams
- **Persists incident data** to the database for historical tracking and audit trails
- **Notifies the Operator Dashboard** to make incidents immediately visible to human operators
- **Updates job status** to mark incidents as processed and ready for response

**Action Generation Guidelines:**
- Provide specific, actionable recommendations tailored to severity level
- Assign clear responsible parties (e.g., Fire Department, Police, Emergency Medical Services)
- Include realistic response timelines based on incident severity and scope
- Prioritize human safety and critical infrastructure protection above all else
- Scale response scope appropriately (e.g., local response for LOW, regional coordination for CRITICAL)

**Communication Template Guidelines:**
- Use professional, clear, and concise language suitable for emergency personnel
- Include all critical incident information (ID, severity level, location, brief summary)
- List the top 3–5 priority actions in order of importance
- Provide contact information placeholders for inter-agency coordination
- Set clear expectations for next status updates and response milestones

**Key Capabilities:**
- Multi-format action generation (structured recommendations for automated systems)
- Template-based communication for rapid team briefing
- Complete incident data persistence for regulatory compliance and post-incident analysis
- Real-time dashboard updates for situational awareness
- Seamless integration with existing emergency response infrastructure

This agent serves as the bridge between intelligent incident analysis and human-driven emergency response, ensuring that operators have everything needed to act decisively and effectively. By automating routine communication and documentation tasks, the Dispatcher Agent frees response teams to focus on saving lives.

### Dashboard Agent Setup
The Dashboard Agent is an additional component in the AgentFleet pipeline. It receives dispatched incidents from the Dispatcher Agent and creates markdown dashboards for human operators to visualize and manage emergency response operations.

The Dashboard Agent performs the following functions:
- **Receives dispatched incidents** from the Dispatcher Agent with recommended actions and communication templates
- **Generates markdown dashboards** that summarize incident details, severity levels, recommended actions, and status updates
- **Organizes dashboards** for easy navigation and quick reference by human operators

