# United Airlines Hackathon - Multi-Agent Operations System

A sophisticated multi-agent system for handling United Airlines flight operations, including intelligent routing, passenger rebooking, crew management, and dispatch operations.

## Key Features

- **Intelligent Routing**: Dynamic workflow sequencing based on operational conditions
- **Weather Alert Integration**: Real-time weather impact assessment
- **FAA Compliance**: Automated crew legality checks with human approval
- **Smart Passenger Rebooking**: Loyalty-tier based reassignment when flights are cancelled, with integrated customer confirmations
- **MCP Architecture**: Seamless database and communication integration

## Getting Started

For detailed setup and running instructions, see the [Quick Start Guide](quickstart_guide.md).

## System Overview

The system consists of five core agents that work together to handle flight disruptions:

### Core Agents

1. **`planner_agent.py`** - **Intelligent Routing & Executive Planner Agent**
   - **Intelligent Workflow Routing**: Dynamically determines optimal agent execution sequence based on operational conditions
   - **Condition-Based Sequencing**: Routes based on weather alerts, crew issues, and flight cancellations
   - **State Management**: Tracks workflow progress and agent completion status
   - **Executive Summaries**: Generates comprehensive reports with both Operations and Customer Rebooking sections
   - **Human-in-the-Loop**: Provides approval steps for critical decisions
   - **Database Integration**: Reads all agent activity logs for comprehensive reporting

2. **`crew_ops_agent.py`** - Crew Operations Agent
   - Handles FAA compliance checks
   - Identifies crew violations (duty hours, rest periods, fatigue)
   - Proposes legal crew substitutions with human-in-the-loop approval
   - Logs all actions for audit purposes

3. **`dispatch_ops_agent.py`** - Dispatch Operations Agent
   - Evaluates overall dispatch readiness
   - Checks crew legality, weather conditions, and fuel status
   - Provides go/no-go decision for flight dispatch
   - Identifies specific violations that need resolution
   - Publishes delay advisories for weather-affected flights

4. **`llm_passenger_rebooking_agent.py`** - Passenger Rebooking Agent
   - Analyzes flight cancellation scenarios
   - Makes intelligent passenger assignments based on loyalty tiers
   - Handles edge cases and special circumstances
   - Updates passenger records in database
   - Includes fallback mechanisms for LLM failures

5. **`confirmation_agent.py`** - Confirmation Agent
   - Sends rebooking proposals to passengers via MCP
   - Collects passenger responses in batches
   - Processes confirmations for database updates
   - Manages communication timing and retry logic
   - Provides human-friendly example messages

### Supporting Services

6. **Database Services** (`services/`)
   - **`database_mcp_server.py`** - Core MCP server for database operations
   - **`database_http_server.py`** - HTTP wrapper for database MCP server (Port 8001)
   - **`database_mcp_client.py`** - HTTP client for database operations
   - Manages passenger records, crew schedules, and flight data
   - Provides agent activity logging and audit trails

7. **Passenger Communications Services** (`services/`)
   - **`passenger_communications_mcp_server.py`** - Core MCP server for passenger communications
   - **`passenger_communications_http_server.py`** - HTTP wrapper for passenger communications (Port 8000)
   - **`passenger_communications_mcp_client.py`** - HTTP client for passenger communications
   - Handles rebooking proposal distribution and response collection
   - Manages communication timing and retry logic

8. **Database Management** (`database/`)
   - **`united_ops.db`** - SQLite database with flight, passenger, and crew data
   - **`restore_database_full.py`** - Cleanup utility for database restoration after tests

## Demo Files and Tests

### 1. `agents/demo_scenario.py` - **Main Demo (Recommended)**
**Purpose:** Complete intelligent routing system demonstration
- **Intelligent Workflow Routing**: Dynamically sequences agents based on operational conditions
- **Weather Alert Handling**: Processes thunderstorms and fog conditions
- **Crew Compliance**: FAA violation detection with human-in-the-loop approval
- **Passenger Rebooking**: Loyalty-based assignment with alternative flights
- **Executive Summary**: Comprehensive Operations and Customer Rebooking reports
- **Professional Output**: Clean console output with minimal debug statements

### Additional Tests
For detailed information about the test suite, including end-to-end rebooking tests, multi-agent workflow tests, and intelligent routing validation, see the [agents/README.md](agents/README.md) file.

## System Architecture

The system uses a modular architecture with:
- **MCP (Model Context Protocol)** servers for database and communications
- **LangGraph** for orchestrating multi-agent workflows
- **Claude AI** for intelligent decision making
- **SQLite** database for data persistence

## Communication Flow

1. **Intelligent Routing**: System analyzes operational conditions and determines workflow sequence
2. **Weather Assessment**: Dispatch operations evaluates weather impact
3. **Crew Compliance**: Crew operations checks FAA compliance with human approval
4. **Flight Cancellation**: Passenger rebooking handles cancellations and finds alternatives
5. **Passenger Communication**: Confirmation agent sends proposals and collects responses
6. **Database Updates**: All changes are recorded in the database
7. **Executive Summary**: Comprehensive report generated for review

This system provides a complete solution for handling flight disruptions while maintaining regulatory compliance and operational efficiency. 