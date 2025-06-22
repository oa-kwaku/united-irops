# United Airlines Multi-Agent System - Technical Documentation

This folder contains the multi-agent system for United Airlines operations. For a high-level overview of the agents, see the [main README](../README.md).

## Demo and Test Files

### 1. `demo_scenario.py` - **Intelligent Routing Demo**
**Purpose:** Complete intelligent routing system demonstration
- **Main demo file** - showcases the complete intelligent routing system
- Demonstrates weather alerts, crew issues, and flight cancellations
- Features intelligent workflow sequencing based on operational conditions
- Includes passenger rebooking with confirmations and database updates
- Generates comprehensive executive summaries
- **Recommended starting point for demonstrations**

### Test Files

2. **`tests/rebooking_end_to_end_test.py`** - Passenger Rebooking Test
   - Tests the passenger rebooking workflow specifically
   - Includes database verification steps
   - Demonstrates the complete passenger communication cycle
   - Validates loyalty-based passenger assignment

3. **`tests/multi_agent_workflow_test.py`** - Multi-Agent Workflow Test
   - Demonstrates how to use all agents together
   - Includes both simple and LangGraph-based workflows
   - Provides comprehensive testing scenarios
   - Tests agent-to-agent communication

4. **`tests/test_intelligent_routing_workflow.py`** - Intelligent Routing Test
   - Tests the intelligent routing system specifically
   - Validates dynamic workflow sequencing
   - Tests condition-based routing logic
   - Ensures proper state management across agents

## Technical Implementation

### State Management

The agents use a shared state dictionary that includes:

- **Crew Operations**: `crew_schedule`, `crew_substitutions`, `legality_flags`
- **Dispatch Operations**: `weather_data`, `fuel_data`, `dispatch_status`, `delay_advisories`
- **Passenger Rebooking**: `flight_cancellation_notification`, `impacted_passengers`, `alternative_flights`, `rebooking_proposals`
- **Confirmation**: `sent_messages`, `confirmations`, `batch_ready`, `all_responses_processed`
- **Planning**: `plan_summary`, `messages`, `workflow_sequence`, `current_step`
- **Workflow Control**: `routing_logic`, `workflow_complete`

### Database Integration

The agents integrate with the United Airlines database through:
- **Database MCP Server**: Handles all database operations
- **Agent Logs**: Tracks all agent activities for audit purposes
- **Passenger Records**: Updates passenger flight assignments
- **Crew Records**: Manages crew schedules and substitutions

### Communication Services

The agents use MCP (Model Context Protocol) services for:
- **Database Operations**: Query and update passenger/crew data
- **Passenger Communications**: Send proposals and collect responses
- **System Coordination**: Share state and coordinate activities

### Error Handling

All agents include comprehensive error handling:
- **Retry Logic**: Automatic retries for network operations
- **Fallback Mechanisms**: Manual processing when LLM agents fail
- **Human-in-the-Loop**: Approval steps for critical decisions
- **Logging**: Detailed logging for debugging and audit purposes
- **Execution Guards**: Prevents duplicate operations

## Running Individual Agents

```bash
# Test planner agent (intelligent routing)
python agents/planner_agent.py

# Test crew operations agent
python agents/crew_ops_agent.py

# Test dispatch operations agent
python agents/dispatch_ops_agent.py

# Test passenger rebooking agent
python agents/llm_passenger_rebooking_agent.py

# Test confirmation agent
python agents/confirmation_agent.py
```

## Workflow Examples

### Main Demo Scenario (Recommended)
```python
from agents.demo_scenario import run_demo_scenario

# Run the complete intelligent routing demo
result = run_demo_scenario()
```

## Testing

The system includes multiple testing levels:
- **Unit Tests**: Individual agent functionality
- **Integration Tests**: Agent-to-agent communication
- **End-to-End Tests**: Complete workflow validation
- **Database Verification**: Confirms data consistency
- **Demo Scenarios**: Real-world operational scenarios

## Output Files

The system generates several output files:
- **Executive Summaries**: Markdown files in `outputs/` directory (absolute path)
- **Agent Logs**: SQLite database with all agent activities
- **System Reports**: Console output with detailed results