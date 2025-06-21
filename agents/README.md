# United Airlines Multi-Agent System

This folder contains the multi-agent system for United Airlines operations, including crew management, dispatch operations, passenger rebooking, and executive planning.

## Agent Overview

### Core Agents

1. **`crew_ops_agent.py`** - Crew Operations Agent
   - Handles FAA compliance checks
   - Identifies crew violations (duty hours, rest periods, fatigue)
   - Proposes legal crew substitutions
   - Logs all actions for audit purposes

2. **`dispatch_ops_agent.py`** - Dispatch Operations Agent
   - Evaluates overall dispatch readiness
   - Checks crew legality, weather conditions, and fuel status
   - Provides go/no-go decision for flight dispatch
   - Identifies specific violations that need resolution

3. **`planner_agent.py`** - Executive Planner Agent
   - Reads all agent activity logs from database
   - Generates executive summaries using Claude
   - Saves summaries to Markdown files
   - Provides human-in-the-loop approval for final plans

4. **`llm_passenger_rebooking_agent.py`** - Passenger Rebooking Agent
   - Analyzes flight cancellation scenarios
   - Makes intelligent passenger assignments based on loyalty tiers
   - Handles edge cases and special circumstances
   - Updates passenger records in database

5. **`confirmation_agent.py`** - Confirmation Agent
   - Sends rebooking proposals to passengers
   - Collects passenger responses in batches
   - Processes confirmations for database updates
   - Manages communication timing and retry logic

### Test Files

6. **`multi_agent_workflow_test.py`** - Multi-Agent Workflow Test
   - Demonstrates how to use all agents together
   - Includes both simple and LangGraph-based workflows
   - Provides comprehensive testing scenarios

7. **`end_to_end_test.py`** - End-to-End Test
   - Tests the passenger rebooking workflow specifically
   - Includes database verification steps
   - Demonstrates the complete passenger communication cycle

8. **`united_ops_agentic_system.py`** - United Airlines Operations Agentic System
   - Contains the workflow graph creation logic
   - Provides execution functions for the multi-agent system
   - Includes sample data and initialization
   - Orchestrates the complete United Airlines operations workflow

## Usage

### Prerequisites

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
# Create a .env file with your Anthropic API key
ANTHROPIC_API_KEY=your_api_key_here
```

3. Ensure the database and services are running:
```bash
# Start the database HTTP server (Port 8001)
python services/database_http_server.py

# Start the passenger communications server (Port 8000)
python services/passenger_communications_http_server.py
```

### Running Individual Agents

```python
# Test crew operations agent
python agents/crew_ops_agent.py

# Test dispatch operations agent
python agents/dispatch_ops_agent.py

# Test planner agent
python agents/planner_agent.py

# Test passenger rebooking agent
python agents/llm_passenger_rebooking_agent.py

# Test confirmation agent
python agents/confirmation_agent.py
```

### Running Multi-Agent Workflows

```python
# Run the simple multi-agent test
python agents/multi_agent_workflow_test.py

# Run the end-to-end passenger rebooking test
python agents/end_to_end_test.py

# Run the full multi-agent system
python agents/united_ops_agentic_system.py
```

## Workflow Examples

### Simple Crew and Planning Workflow
```python
from agents.united_ops_agentic_system import run_multi_agent_system

# Run simple workflow (crew ops + planner only)
result = run_multi_agent_system("simple")
```

### Full Multi-Agent Workflow
```python
from agents.united_ops_agentic_system import run_multi_agent_system

# Run complete workflow (all agents)
result = run_multi_agent_system("full")
```

### Custom Workflow with LangGraph
```python
from agents.multi_agent_workflow_test import run_multi_agent_workflow_test

# Run the comprehensive LangGraph workflow
result = run_multi_agent_workflow_test()
```

## State Management

The agents use a shared state dictionary that includes:

- **Crew Operations**: `crew_schedule`, `crew_substitutions`, `legality_flags`
- **Dispatch Operations**: `weather_data`, `fuel_data`, `dispatch_status`
- **Passenger Rebooking**: `flight_cancellation_notification`, `rebooking_proposals`
- **Confirmation**: `sent_messages`, `confirmations`, `batch_ready`
- **Planning**: `plan_summary`, `messages`

## Database Integration

The agents integrate with the United Airlines database through:
- **Database MCP Server**: Handles all database operations
- **Agent Logs**: Tracks all agent activities for audit purposes
- **Passenger Records**: Updates passenger flight assignments
- **Crew Records**: Manages crew schedules and substitutions

## Communication Services

The agents use MCP (Model Context Protocol) services for:
- **Database Operations**: Query and update passenger/crew data
- **Passenger Communications**: Send proposals and collect responses
- **System Coordination**: Share state and coordinate activities

## Error Handling

All agents include comprehensive error handling:
- **Retry Logic**: Automatic retries for network operations
- **Fallback Mechanisms**: Manual processing when LLM agents fail
- **Human-in-the-Loop**: Approval steps for critical decisions
- **Logging**: Detailed logging for debugging and audit purposes

## Testing

The system includes multiple testing levels:
- **Unit Tests**: Individual agent functionality
- **Integration Tests**: Agent-to-agent communication
- **End-to-End Tests**: Complete workflow validation
- **Database Verification**: Confirms data consistency

## Output Files

The system generates several output files:
- **Executive Summaries**: Markdown files in `outputs/` directory
- **Agent Logs**: SQLite database with all agent activities
- **System Reports**: Console output with detailed results 