# United Airlines Services

This folder contains the core services for the United Airlines passenger rebooking system.

## Services Overview

### Database Services
- **`database_mcp_server.py`** - Core MCP server for database operations
- **`database_http_server.py`** - HTTP wrapper for database MCP server (Port 8001)
- **`database_mcp_client.py`** - HTTP client for database operations

### Passenger Communications Services
- **`passenger_communications_mcp_server.py`** - Core MCP server for passenger communications
- **`passenger_communications_http_server.py`** - HTTP wrapper for passenger communications (Port 8000)
- **`passenger_communications_mcp_client.py`** - HTTP client for passenger communications


## Integration

The services are used by the agents in the `../agents/` folder:
- `llm_passenger_rebooking_agent.py` uses the database client
- `confirmation_agent.py` uses the passenger communications client
- `end_to_end_test.py` runs the complete workflow 