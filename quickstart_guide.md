# Quick Start Guide

This guide will help you get the United Airlines Multi-Agent Operations System up and running quickly.

## Prerequisites

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root with your Anthropic API key:

```bash
# Create a .env file with your Anthropic API key
ANTHROPIC_API_KEY=your_api_key_here
```

## Starting the Services

You need to run two services in separate terminals:

### Terminal 1 - Passenger Communications Server

```bash
cd services
python passenger_communications_http_server.py
```

This starts the passenger communications MCP server on port 8000.

### Terminal 2 - Database Server

```bash
cd services
python database_http_server.py
```

This starts the database MCP server on port 8001.

## Running the Main Demo

### Terminal 3 - Main Demo

```bash
python agents/demo_scenario.py
```

This runs the complete intelligent routing demo showcasing:
- Weather alert handling
- Crew compliance checks with human approval
- Flight cancellation and passenger rebooking
- Executive summary generation

## What the Demo Shows

The main demo (`agents/demo_scenario.py`) demonstrates:

- **Intelligent Workflow Routing**: Dynamically sequences agents based on operational conditions
- **Weather Alert Handling**: Processes thunderstorms and fog conditions
- **Crew Compliance**: FAA violation detection with human-in-the-loop approval
- **Passenger Rebooking**: Loyalty-based assignment with alternative flights
- **Executive Summary**: Comprehensive Operations and Customer Rebooking reports
- **Professional Output**: Clean console output with minimal debug statements

## Running Individual Agents

You can also test individual agents:

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

## Troubleshooting

### Common Issues

1. **API Key Not Found**: Make sure your `.env` file contains the `ANTHROPIC_API_KEY`
2. **Port Already in Use**: Ensure ports 8000 and 8001 are available
3. **Database Connection Error**: Make sure the database server is running
4. **Module Not Found**: Ensure you're running commands from the project root directory

### Service Status

To check if services are running:
- Passenger Communications: `http://localhost:8000/health`
- Database Server: `http://localhost:8001/health`

## Next Steps

After running the demo successfully:
1. Review the generated executive summary in the `outputs/` directory
2. Explore the individual agents to understand their capabilities
3. Check the [agents/README.md](agents/README.md) for detailed technical information
4. Run the test suite to validate system functionality

## System Architecture

The system uses:
- **MCP (Model Context Protocol)** servers for database and communications
- **LangGraph** for orchestrating multi-agent workflows
- **Claude AI** for intelligent decision making
- **SQLite** database for data persistence

This provides a complete solution for handling flight disruptions while maintaining regulatory compliance and operational efficiency. 