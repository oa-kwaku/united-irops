"""
United Airlines Database MCP Server

This MCP server exposes database operations as standardized tools
that AI agents can discover and use. This will be the foundation
for proper MCP database integration, especially when moving to GCP.
"""

import sqlite3
import logging
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class DatabaseTool:
    """Represents a database operation as an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]

class UnitedAirlinesDatabaseMCPServer:
    """
    MCP server for United Airlines database operations.
    Exposes database queries and updates as standardized tools.
    """
    
    def __init__(self, db_path: str = "../database/united_ops.db"):
        self.db_path = db_path
        self.tools = self._initialize_tools()
        logger.info(f"🚀 United Airlines Database MCP Server initialized with {len(self.tools)} tools")
    
    def _initialize_tools(self) -> List[DatabaseTool]:
        """Initialize all available database tools."""
        return [
            DatabaseTool(
                name="query_passengers",
                description="Query passengers with optional filters for flight_number, loyalty_tier, etc.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "flight_number": {"type": "string", "description": "Flight number to filter by"},
                        "loyalty_tier": {"type": "string", "description": "Loyalty tier to filter by (1K, Gold, Silver, etc.)"},
                        "limit": {"type": "integer", "description": "Maximum number of results to return"}
                    }
                },
                handler=self._query_passengers
            ),
            DatabaseTool(
                name="query_flights",
                description="Query flights with optional filters for departure_location, arrival_location, status, etc.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "departure_location": {"type": "string", "description": "Departure airport code"},
                        "arrival_location": {"type": "string", "description": "Arrival airport code"},
                        "status": {"type": "string", "description": "Flight status (scheduled, delayed, cancelled, etc.)"},
                        "limit": {"type": "integer", "description": "Maximum number of results to return"}
                    }
                },
                handler=self._query_flights
            ),
            DatabaseTool(
                name="update_passenger_flight",
                description="Update a passenger's flight assignment.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "passenger_id": {"type": "string", "description": "Passenger ID to update"},
                        "new_flight": {"type": "string", "description": "New flight number"},
                        "reason": {"type": "string", "description": "Reason for the update (optional)"}
                    },
                    "required": ["passenger_id", "new_flight"]
                },
                handler=self._update_passenger_flight
            ),
            DatabaseTool(
                name="get_available_seats",
                description="Get number of available seats on a specific flight.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "flight_number": {"type": "string", "description": "Flight number to check"}
                    },
                    "required": ["flight_number"]
                },
                handler=self._get_available_seats
            ),
            DatabaseTool(
                name="get_flight_details",
                description="Get detailed information about a specific flight.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "flight_number": {"type": "string", "description": "Flight number to get details for"}
                    },
                    "required": ["flight_number"]
                },
                handler=self._get_flight_details
            ),
            DatabaseTool(
                name="get_passenger_count",
                description="Get the number of passengers on a specific flight.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "flight_number": {"type": "string", "description": "Flight number to count passengers for"}
                    },
                    "required": ["flight_number"]
                },
                handler=self._get_passenger_count
            )
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools in MCP format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            for tool in self.tools
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool with given parameters."""
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = tool.handler(parameters)
                    return {
                        "success": True,
                        "tool": tool_name,
                        "result": result,
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    logger.error(f"❌ Error executing tool {tool_name}: {e}")
                    return {
                        "success": False,
                        "tool": tool_name,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
        
        return {
            "success": False,
            "tool": tool_name,
            "error": f"Tool '{tool_name}' not found",
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def _query_passengers(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query passengers with optional filters."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM passengers WHERE 1=1"
            query_params = []
            
            if "flight_number" in params:
                query += " AND flight_number = ?"
                query_params.append(params["flight_number"])
            
            if "loyalty_tier" in params:
                query += " AND loyalty_tier = ?"
                query_params.append(params["loyalty_tier"])
            
            if "limit" in params:
                query += f" LIMIT {params['limit']}"
            
            df = pd.read_sql_query(query, conn, params=query_params)
            result = df.to_dict('records')
            
            logger.info(f"📊 Query passengers: {len(result)} results")
            return result
            
        finally:
            conn.close()
    
    def _query_flights(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query flights with optional filters."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM flights WHERE 1=1"
            query_params = []
            
            if "departure_location" in params:
                query += " AND departure_location = ?"
                query_params.append(params["departure_location"])
            
            if "arrival_location" in params:
                query += " AND arrival_location = ?"
                query_params.append(params["arrival_location"])
            
            if "status" in params:
                query += " AND status = ?"
                query_params.append(params["status"])
            
            if "limit" in params:
                query += f" LIMIT {params['limit']}"
            
            df = pd.read_sql_query(query, conn, params=query_params)
            result = df.to_dict('records')
            
            logger.info(f"✈️ Query flights: {len(result)} results")
            return result
            
        finally:
            conn.close()
    
    def _update_passenger_flight(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update a passenger's flight assignment."""
        conn = self._get_connection()
        try:
            passenger_id = params["passenger_id"]
            new_flight = params["new_flight"]
            reason = params.get("reason", "No reason provided")
            
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE passengers SET flight_number = ? WHERE passenger_id = ?",
                (new_flight, passenger_id)
            )
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"✅ Updated passenger {passenger_id} to flight {new_flight}")
                return {
                    "success": True,
                    "passenger_id": passenger_id,
                    "new_flight": new_flight,
                    "reason": reason,
                    "rows_affected": cursor.rowcount
                }
            else:
                logger.warning(f"⚠️ No passenger found with ID {passenger_id}")
                return {
                    "success": False,
                    "passenger_id": passenger_id,
                    "error": "Passenger not found",
                    "rows_affected": 0
                }
                
        finally:
            conn.close()
    
    def _get_available_seats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get number of available seats on a specific flight."""
        conn = self._get_connection()
        try:
            flight_number = params["flight_number"]
            
            # Get flight details
            flight_query = "SELECT available_seats FROM flights WHERE flight_number = ?"
            flight_df = pd.read_sql_query(flight_query, conn, params=[flight_number])
            
            if len(flight_df) == 0:
                return {
                    "success": False,
                    "flight_number": flight_number,
                    "error": "Flight not found"
                }
            
            available_seats = flight_df.iloc[0]['available_seats']
            
            logger.info(f"💺 Flight {flight_number}: {available_seats} available seats")
            return {
                "success": True,
                "flight_number": flight_number,
                "available_seats": int(available_seats)
            }
            
        finally:
            conn.close()
    
    def _get_flight_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a specific flight."""
        conn = self._get_connection()
        try:
            flight_number = params["flight_number"]
            
            query = "SELECT * FROM flights WHERE flight_number = ?"
            df = pd.read_sql_query(query, conn, params=[flight_number])
            
            if len(df) == 0:
                return {
                    "success": False,
                    "flight_number": flight_number,
                    "error": "Flight not found"
                }
            
            flight_details = df.iloc[0].to_dict()
            
            logger.info(f"✈️ Retrieved details for flight {flight_number}")
            return {
                "success": True,
                "flight_number": flight_number,
                "details": flight_details
            }
            
        finally:
            conn.close()
    
    def _get_passenger_count(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get the number of passengers on a specific flight."""
        conn = self._get_connection()
        try:
            flight_number = params["flight_number"]
            
            query = "SELECT COUNT(*) as passenger_count FROM passengers WHERE flight_number = ?"
            df = pd.read_sql_query(query, conn, params=[flight_number])
            
            passenger_count = df.iloc[0]['passenger_count']
            
            logger.info(f"👥 Flight {flight_number}: {passenger_count} passengers")
            return {
                "success": True,
                "flight_number": flight_number,
                "passenger_count": int(passenger_count)
            }
            
        finally:
            conn.close()

# Global instance
_database_mcp_server = None

def get_database_mcp_server() -> UnitedAirlinesDatabaseMCPServer:
    """Get the global database MCP server instance."""
    global _database_mcp_server
    if _database_mcp_server is None:
        _database_mcp_server = UnitedAirlinesDatabaseMCPServer()
    return _database_mcp_server

def test_database_mcp_server():
    """Test the database MCP server functionality."""
    print("🧪 Testing United Airlines Database MCP Server")
    print("=" * 60)
    
    server = UnitedAirlinesDatabaseMCPServer()
    
    # Test 1: Get available tools
    print("📋 Available Tools:")
    tools = server.get_tools()
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    # Test 2: Query passengers
    print("\n🔍 Testing query_passengers tool:")
    result = server.execute_tool("query_passengers", {"flight_number": "DL7016", "limit": 5})
    print(f"  Result: {result}")
    
    # Test 3: Get flight details
    print("\n✈️ Testing get_flight_details tool:")
    result = server.execute_tool("get_flight_details", {"flight_number": "DL7016"})
    print(f"  Result: {result}")
    
    # Test 4: Get available seats
    print("\n💺 Testing get_available_seats tool:")
    result = server.execute_tool("get_available_seats", {"flight_number": "DL7016"})
    print(f"  Result: {result}")
    
    # Test 5: Get passenger count
    print("\n👥 Testing get_passenger_count tool:")
    result = server.execute_tool("get_passenger_count", {"flight_number": "DL7016"})
    print(f"  Result: {result}")
    
    print("\n✅ Database MCP Server test completed!")
    print("\n📋 Usage Examples:")
    print("  - Query passengers on flight: {'flight_number': 'DL7016', 'limit': 10}")
    print("  - Get flight details: {'flight_number': 'DL7016'}")
    print("  - Update passenger flight: {'passenger_id': 'PAX001', 'new_flight': 'UA200'}")
    print("  - Get available seats: {'flight_number': 'DL7016'}")
    print("  - Get passenger count: {'flight_number': 'DL7016'}")

if __name__ == "__main__":
    test_database_mcp_server() 