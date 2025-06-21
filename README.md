# United Airlines Hackathon - Multi-Agent Operations System

A sophisticated multi-agent system for handling United Airlines flight operations, including passenger rebooking, crew management, and dispatch operations.

## Quick Start

### 1. Start the Services

You need to run two services in separate terminals:

**Terminal 1 - Passenger Communications Server:**
```bash
cd services
python passenger_communications_http_server.py
```
This starts the passenger communications MCP server on port 8000.

**Terminal 2 - Database Server:**
```bash
cd services
python database_http_server.py
```
This starts the database MCP server on port 8001.

### 2. Run Tests

Navigate to the agents folder and run any of the test files:

```bash
cd agents
```

## Test Files

### 1. `rebooking_end_to_end_test.py`
**Purpose:** Complete end-to-end passenger rebooking workflow
- Simulates a flight cancellation
- Finds alternative flights
- Assigns passengers based on loyalty tiers
- Sends rebooking proposals to passengers
- Processes passenger confirmations
- Updates database with final assignments

### 2. `multi_agent_workflow_test.py`
**Purpose:** Tests the new United Airlines operations agents
- Runs FAA compliance checks for crew
- Performs dispatch readiness evaluations
- Generates executive summaries
- Tests the complete multi-agent workflow

### 3. `simple_test_multi_agent_workflow.py`
**Purpose:** Simplified test of the multi-agent system
- Basic workflow testing without complex scenarios
- Good for initial system validation
- Faster execution for development

## Agents Overview

### Core Rebooking Agents

**`llm_passenger_rebooking_agent.py`**
- Intelligent passenger rebooking using Claude AI
- Analyzes flight cancellations and finds alternatives
- Assigns passengers based on loyalty tiers and preferences
- Handles edge cases and provides explanations

**`confirmation_agent.py`**
- Manages passenger communications
- Sends rebooking proposals to passengers
- Collects and processes passenger responses
- Handles batch processing for efficiency

### United Airlines Operations Agents

**`crew_ops_agent.py`**
- FAA compliance monitoring for crew schedules
- Identifies crew duty time violations
- Proposes legal crew substitutions
- Ensures regulatory compliance

**`dispatch_ops_agent.py`**
- Pre-flight dispatch readiness checks
- Evaluates crew legality, weather, and fuel status
- Provides overall dispatch approval
- Identifies potential operational issues

**`planner_agent.py`**
- Generates executive summaries of operations
- Reads system-wide activity logs
- Provides human-in-the-loop approval
- Creates comprehensive operational reports

### System Architecture

The system uses a modular architecture with:
- **MCP (Model Context Protocol)** servers for database and communications
- **LangGraph** for orchestrating multi-agent workflows
- **Claude AI** for intelligent decision making
- **SQLite** database for data persistence

### Key Features

- **Intelligent Rebooking:** AI-powered passenger assignment based on loyalty tiers
- **FAA Compliance:** Automated crew legality checking and substitution
- **Dispatch Operations:** Comprehensive pre-flight readiness evaluation
- **Human-in-the-Loop:** Executive approval for critical decisions
- **Scalable Architecture:** MCP-based services for easy integration

### Database Schema

The system uses three main tables:
- **passengers:** Passenger information and flight assignments
- **flights:** Flight details and availability
- **crew:** Crew member information and duty assignments

### Communication Flow

1. Flight cancellation detected
2. LLM agent analyzes situation and finds alternatives
3. Passengers assigned to new flights based on loyalty
4. Confirmation agent sends proposals to passengers
5. Responses collected and processed
6. Database updated with final assignments
7. Operations agents ensure compliance and readiness
8. Executive summary generated for review

This system provides a complete solution for handling flight disruptions while maintaining regulatory compliance and operational efficiency. 