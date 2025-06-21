"""
HTTP Server wrapper for the United Airlines Database MCP Server.

This provides HTTP endpoints that agents can call to interact with the database
through standardized MCP tools.
"""

from flask import Flask, request, jsonify
import logging
from database_mcp_server import UnitedAirlinesDatabaseMCPServer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Global MCP server instance
mcp_server = None

@app.before_first_request
def initialize_mcp_server():
    """Initialize the database MCP server before the first request."""
    global mcp_server
    if mcp_server is None:
        mcp_server = UnitedAirlinesDatabaseMCPServer()
        logger.info("🚀 Database MCP server initialized")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "running": True})

@app.route('/tools', methods=['GET'])
def get_available_tools():
    """Get all available database tools."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        tools = mcp_server.get_tools()
        return jsonify({
            "tools": tools,
            "count": len(tools)
        })
        
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/execute/<tool_name>', methods=['POST'])
def execute_tool(tool_name):
    """Execute a specific database tool."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        # Get parameters from request body
        parameters = request.get_json() or {}
        
        # Execute the tool
        result = mcp_server.execute_tool(tool_name, parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return jsonify({"error": str(e)}), 500

# Convenience endpoints for common operations
@app.route('/passengers', methods=['GET'])
def query_passengers():
    """Query passengers with optional filters."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        # Get query parameters
        flight_number = request.args.get('flight_number')
        loyalty_tier = request.args.get('loyalty_tier')
        limit = request.args.get('limit', type=int)
        
        parameters = {}
        if flight_number:
            parameters['flight_number'] = flight_number
        if loyalty_tier:
            parameters['loyalty_tier'] = loyalty_tier
        if limit:
            parameters['limit'] = limit
        
        result = mcp_server.execute_tool("query_passengers", parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error querying passengers: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/flights', methods=['GET'])
def query_flights():
    """Query flights with optional filters."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        # Get query parameters
        departure_location = request.args.get('departure_location')
        arrival_location = request.args.get('arrival_location')
        status = request.args.get('status')
        limit = request.args.get('limit', type=int)
        
        parameters = {}
        if departure_location:
            parameters['departure_location'] = departure_location
        if arrival_location:
            parameters['arrival_location'] = arrival_location
        if status:
            parameters['status'] = status
        if limit:
            parameters['limit'] = limit
        
        result = mcp_server.execute_tool("query_flights", parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error querying flights: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/passengers/<passenger_id>/flight', methods=['PUT'])
def update_passenger_flight(passenger_id):
    """Update a passenger's flight assignment."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        # Get parameters from request body
        data = request.get_json() or {}
        new_flight = data.get('new_flight')
        reason = data.get('reason', 'No reason provided')
        
        if not new_flight:
            return jsonify({"error": "new_flight parameter is required"}), 400
        
        parameters = {
            "passenger_id": passenger_id,
            "new_flight": new_flight,
            "reason": reason
        }
        
        result = mcp_server.execute_tool("update_passenger_flight", parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating passenger flight: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/flights/<flight_number>/seats', methods=['GET'])
def get_available_seats(flight_number):
    """Get available seats for a specific flight."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        parameters = {"flight_number": flight_number}
        result = mcp_server.execute_tool("get_available_seats", parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting available seats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/flights/<flight_number>', methods=['GET'])
def get_flight_details(flight_number):
    """Get detailed information about a specific flight."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        parameters = {"flight_number": flight_number}
        result = mcp_server.execute_tool("get_flight_details", parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting flight details: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/flights/<flight_number>/passengers', methods=['GET'])
def get_passenger_count(flight_number):
    """Get the number of passengers on a specific flight."""
    try:
        if mcp_server is None:
            return jsonify({"error": "Database MCP server not initialized"}), 500
        
        parameters = {"flight_number": flight_number}
        result = mcp_server.execute_tool("get_passenger_count", parameters)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting passenger count: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the database MCP server."""
    try:
        global mcp_server
        if mcp_server:
            mcp_server = None
            logger.info("🛑 Database MCP server stopped")
        return jsonify({"status": "shutdown"})
        
    except Exception as e:
        logger.error(f"Error shutting down database MCP server: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting United Airlines Database HTTP Server")
    print("=" * 60)
    print("Endpoints:")
    print("  GET  /health                           - Health check")
    print("  GET  /tools                            - Get available tools")
    print("  POST /execute/<tool_name>              - Execute any tool")
    print("  GET  /passengers                       - Query passengers")
    print("  GET  /flights                          - Query flights")
    print("  PUT  /passengers/<id>/flight           - Update passenger flight")
    print("  GET  /flights/<number>/seats           - Get available seats")
    print("  GET  /flights/<number>                 - Get flight details")
    print("  GET  /flights/<number>/passengers      - Get passenger count")
    print("  POST /shutdown                         - Shutdown server")
    print("=" * 60)
    
    # Initialize MCP server
    mcp_server = UnitedAirlinesDatabaseMCPServer()
    
    try:
        # Run Flask app
        app.run(host='0.0.0.0', port=8001, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        if mcp_server:
            mcp_server = None
        print("✅ Server stopped") 