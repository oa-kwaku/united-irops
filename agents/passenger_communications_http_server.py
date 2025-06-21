"""
HTTP Server wrapper for the Passenger Communications MCP Server.

This provides HTTP endpoints that the MCP client can call.
"""

from flask import Flask, request, jsonify
import logging
from passenger_communications_mcp_server import PassengerCommunicationsMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Global MCP server instance
mcp_server = None

@app.before_first_request
def initialize_mcp_server():
    """Initialize the MCP server before the first request."""
    global mcp_server
    if mcp_server is None:
        mcp_server = PassengerCommunicationsMCP()
        mcp_server.start()
        logger.info("🚀 MCP server initialized and started")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "running": True})

@app.route('/send_rebooking_proposal', methods=['POST'])
def send_rebooking_proposal():
    """Send a rebooking proposal to the MCP server."""
    try:
        proposal = request.get_json()
        if not proposal:
            return jsonify({"error": "No proposal data provided"}), 400
        
        # Validate required fields
        required_fields = ['passenger_id', 'original_flight', 'rebooked_flight', 'arrival_location']
        for field in required_fields:
            if field not in proposal:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Ensure MCP server is initialized
        if mcp_server is None:
            return jsonify({"error": "MCP server not initialized"}), 500
        
        # Send to MCP server
        result = mcp_server.send_rebooking_proposal(proposal)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error sending rebooking proposal: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_passenger_response', methods=['GET'])
def get_passenger_response():
    """Get passenger response from the MCP server."""
    try:
        message_id = request.args.get('message_id')
        timeout = float(request.args.get('timeout', 30.0))
        
        if not message_id:
            return jsonify({"error": "No message_id provided"}), 400
        
        # Ensure MCP server is initialized
        if mcp_server is None:
            return jsonify({"error": "MCP server not initialized"}), 500
        
        # Get response from MCP server
        response = mcp_server.get_passenger_response(message_id, timeout)
        if response:
            return jsonify(response)
        else:
            return jsonify({"status": "pending", "message": "Response not ready"}), 202
        
    except Exception as e:
        logger.error(f"Error getting passenger response: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_available_responses', methods=['GET'])
def get_all_available_responses():
    """Get all available responses from the MCP server."""
    try:
        # Ensure MCP server is initialized
        if mcp_server is None:
            return jsonify({"error": "MCP server not initialized"}), 500
        
        # Get all available responses from MCP server
        responses = mcp_server.get_all_available_responses()
        return jsonify({
            "responses": responses,
            "count": len(responses)
        })
        
    except Exception as e:
        logger.error(f"Error getting all available responses: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_system_status', methods=['GET'])
def get_system_status():
    """Get system status from the MCP server."""
    try:
        # Ensure MCP server is initialized
        if mcp_server is None:
            return jsonify({"error": "MCP server not initialized"}), 500
        
        status = mcp_server.get_system_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the MCP server."""
    try:
        global mcp_server
        if mcp_server:
            mcp_server.stop()
            mcp_server = None
            logger.info("🛑 MCP server stopped")
        return jsonify({"status": "shutdown"})
        
    except Exception as e:
        logger.error(f"Error shutting down MCP server: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Passenger Communications HTTP Server")
    print("=" * 60)
    print("Endpoints:")
    print("  GET  /health                    - Health check")
    print("  POST /send_rebooking_proposal   - Send rebooking proposal")
    print("  GET  /get_passenger_response    - Get passenger response")
    print("  GET  /get_system_status         - Get system status")
    print("  POST /shutdown                  - Shutdown server")
    print("=" * 60)
    
    # Initialize MCP server
    mcp_server = PassengerCommunicationsMCP(response_delay_range=(0, 0))  # Instant responses for testing
    mcp_server.start()
    
    try:
        # Run Flask app
        app.run(host='0.0.0.0', port=8000, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        if mcp_server:
            mcp_server.stop()
        print("✅ Server stopped") 