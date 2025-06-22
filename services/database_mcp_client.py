"""
Database MCP Client

This is an MCP client that allows agents to communicate
with the database MCP server via HTTP.
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseMCPClient:
    """
    MCP client for communicating with the database server.
    """
    
    def __init__(self, server_url: str = "http://localhost:8001", timeout: int = 30, max_retries: int = 3, retry_delay: float = 1.0):
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a database tool with retry logic.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Dictionary with tool execution result
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    f"{self.server_url}/execute/{tool_name}",
                    json=parameters,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"🗄️ Database Client: Executed {tool_name}")
                return result
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ Database Client: Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ Database Client: All {self.max_retries} attempts failed")
                    raise RuntimeError(f"Failed to execute {tool_name} after {self.max_retries} attempts: {e}")
        
        # This should never be reached due to the raise statement above, but needed for type checking
        raise RuntimeError("Unexpected error in execute_tool")
    
    def query_passengers(self, flight_number: Optional[str] = None, loyalty_tier: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query passengers with optional filters.
        
        Args:
            flight_number: Flight number to filter by
            loyalty_tier: Loyalty tier to filter by
            limit: Maximum number of results
            
        Returns:
            List of passenger dictionaries
        """
        params = {}
        if flight_number:
            params['flight_number'] = flight_number
        if loyalty_tier:
            params['loyalty_tier'] = loyalty_tier
        if limit:
            params['limit'] = limit
        
        result = self.execute_tool("query_passengers", params)
        return result.get("result", [])
    
    def query_flights(self, departure_location: Optional[str] = None, arrival_location: Optional[str] = None, status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query flights with optional filters.
        
        Args:
            departure_location: Departure airport code
            arrival_location: Arrival airport code
            status: Flight status
            limit: Maximum number of results
            
        Returns:
            List of flight dictionaries
        """
        params = {}
        if departure_location:
            params['departure_location'] = departure_location
        if arrival_location:
            params['arrival_location'] = arrival_location
        if status:
            params['status'] = status
        if limit:
            params['limit'] = limit
        
        result = self.execute_tool("query_flights", params)
        return result.get("result", [])
    
    def query_crew(self, assigned_flight: Optional[str] = None, role: Optional[str] = None, base: Optional[str] = None, 
                   min_rest_hours: Optional[float] = None, max_fatigue_score: Optional[float] = None, 
                   has_duty_assignment: Optional[bool] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query crew with optional filters.
        
        Args:
            assigned_flight: Flight number to filter by (use None for unassigned)
            role: Crew role to filter by (Pilot, Attendant, etc.)
            base: Crew base to filter by
            min_rest_hours: Minimum rest hours required
            max_fatigue_score: Maximum fatigue score allowed
            has_duty_assignment: Filter for crew with duty assignments
            limit: Maximum number of results
            
        Returns:
            List of crew dictionaries
        """
        params = {}
        if assigned_flight is not None:
            params['assigned_flight'] = assigned_flight
        if role:
            params['role'] = role
        if base:
            params['base'] = base
        if min_rest_hours is not None:
            params['min_rest_hours'] = min_rest_hours
        if max_fatigue_score is not None:
            params['max_fatigue_score'] = max_fatigue_score
        if has_duty_assignment is not None:
            params['has_duty_assignment'] = has_duty_assignment
        if limit:
            params['limit'] = limit
        
        result = self.execute_tool("query_crew", params)
        return result.get("result", [])
    
    def update_passenger_flight(self, passenger_id: str, new_flight: str, reason: str = "No reason provided") -> Dict[str, Any]:
        """
        Update a passenger's flight assignment.
        
        Args:
            passenger_id: Passenger ID to update
            new_flight: New flight number
            reason: Reason for the update
            
        Returns:
            Update result dictionary
        """
        params = {
            "passenger_id": passenger_id,
            "new_flight": new_flight,
            "reason": reason
        }
        
        result = self.execute_tool("update_passenger_flight", params)
        return result.get("result", {})
    
    def get_available_seats(self, flight_number: str) -> Dict[str, Any]:
        """
        Get number of available seats on a specific flight.
        
        Args:
            flight_number: Flight number to check
            
        Returns:
            Dictionary with available seats information
        """
        params = {"flight_number": flight_number}
        result = self.execute_tool("get_available_seats", params)
        return result.get("result", {})
    
    def get_flight_details(self, flight_number: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific flight.
        
        Args:
            flight_number: Flight number to get details for
            
        Returns:
            Dictionary with flight details
        """
        params = {"flight_number": flight_number}
        result = self.execute_tool("get_flight_details", params)
        return result.get("result", {})
    
    def get_passenger_count(self, flight_number: str) -> Dict[str, Any]:
        """
        Get the number of passengers on a specific flight.
        
        Args:
            flight_number: Flight number to count passengers for
            
        Returns:
            Dictionary with passenger count information
        """
        params = {"flight_number": flight_number}
        result = self.execute_tool("get_passenger_count", params)
        return result.get("result", {})
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get all available database tools.
        
        Returns:
            List of available tools
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    f"{self.server_url}/tools",
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("tools", [])
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ Database Client: Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ Database Client: All {self.max_retries} attempts failed")
                    return []
        
        return []
    
    def is_available(self) -> bool:
        """Check if the database MCP server is available with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(f"{self.server_url}/health", timeout=5)
                return response.status_code == 200
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ Database Client: Health check attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        return False

# Global client instance
_database_client = None

def get_database_client() -> DatabaseMCPClient:
    """
    Get the global database MCP client instance.
    
    Returns:
        Database MCP client instance
    """
    global _database_client
    if _database_client is None:
        _database_client = DatabaseMCPClient()
    return _database_client

def test_database_client():
    """Test the database MCP client functionality."""
    print("🧪 Testing Database MCP Client")
    print("=" * 60)
    
    client = DatabaseMCPClient()
    
    # Test availability
    print("🔍 Testing server availability...")
    if client.is_available():
        print("✅ Database MCP server is available")
    else:
        print("❌ Database MCP server is not available")
        print("Note: This is expected if no database MCP server is running")
        return
    
    # Test 1: Get available tools
    print("\n📋 Available Tools:")
    tools = client.get_available_tools()
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    # Test 2: Query passengers
    print("\n🔍 Testing query_passengers:")
    passengers = client.query_passengers(flight_number="UA70161", limit=5)
    print(f"  Found {len(passengers)} passengers on flight UA70161")
    
    # Test 3: Get flight details
    print("\n✈️ Testing get_flight_details:")
    flight_details = client.get_flight_details("UA70161")
    if flight_details.get("success"):
        details = flight_details.get("details", {})
        print(f"  Flight UA70161: {details.get('departure_location')} → {details.get('arrival_location')}")
        print(f"  Status: {details.get('status')}, Available seats: {details.get('available_seats')}")
    else:
        print(f"  Error: {flight_details.get('error', 'Unknown error')}")
    
    # Test 4: Get available seats
    print("\n💺 Testing get_available_seats:")
    seats_info = client.get_available_seats("UA70161")
    if seats_info.get("success"):
        print(f"  Flight UA70161: {seats_info.get('available_seats')} available seats")
    else:
        print(f"  Error: {seats_info.get('error', 'Unknown error')}")
    
    # Test 5: Get passenger count
    print("\n👥 Testing get_passenger_count:")
    passenger_count = client.get_passenger_count("UA70161")
    if passenger_count.get("success"):
        print(f"  Flight UA70161: {passenger_count.get('passenger_count')} passengers")
    else:
        print(f"  Error: {passenger_count.get('error', 'Unknown error')}")
    
    print("\n✅ Database MCP Client test completed!")

if __name__ == "__main__":
    test_database_client() 