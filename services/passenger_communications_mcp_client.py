"""
Passenger Communications MCP Client

This is an MCP client that allows the confirmation agent to communicate
with the passenger communications MCP server.
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

class PassengerCommunicationsMCPClient:
    """
    MCP client for communicating with the passenger communications server.
    """
    
    def __init__(self, server_url: str = "http://localhost:8000", timeout: int = 30, max_retries: int = 3, retry_delay: float = 0.0):
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self._suppress_logging = False
    
    def suppress_logging(self, suppress: bool = True):
        """Temporarily suppress logging for batch operations."""
        self._suppress_logging = suppress
    
    def send_rebooking_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a rebooking proposal to the passenger communications server with retry logic.
        
        Args:
            proposal: Dictionary containing rebooking proposal details
            
        Returns:
            Dictionary with message_id and status
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    f"{self.server_url}/send_rebooking_proposal",
                    json=proposal,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                if not self._suppress_logging:
                    logger.info(f"📨 MCP Client: Sent proposal for {proposal.get('passenger_name', proposal['passenger_id'])}")
                return result
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ MCP Client: Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ MCP Client: All {self.max_retries} attempts failed")
                    raise RuntimeError(f"Failed to send proposal after {self.max_retries} attempts: {e}")
        
        # This should never be reached due to the raise statement above, but needed for type checking
        raise RuntimeError("Unexpected error in send_rebooking_proposal")
    
    def get_passenger_response(self, message_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Get passenger response from the server with retry logic.
        
        Args:
            message_id: ID of the message to get response for
            timeout: Timeout in seconds
            
        Returns:
            Response dictionary or None if not available
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    f"{self.server_url}/get_passenger_response",
                    params={"message_id": message_id, "timeout": timeout},
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                if result.get("status") == "completed":
                    logger.info(f"📤 MCP Client: Received response for message {message_id[:8]}...")
                    return result
                else:
                    logger.debug(f"⏳ MCP Client: Response not ready for message {message_id[:8]}...")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ MCP Client: Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ MCP Client: All {self.max_retries} attempts failed")
                    return None
    
    def get_all_available_responses(self) -> List[Dict[str, Any]]:
        """
        Get all available responses from the server with retry logic.
        
        Returns:
            List of response dictionaries for completed messages
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    f"{self.server_url}/get_all_available_responses",
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                responses = result.get("responses", [])
                
                if responses:
                    logger.info(f"📤 MCP Client: Received {len(responses)} available responses")
                else:
                    logger.debug(f"⏳ MCP Client: No responses ready")
                
                return responses
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ MCP Client: Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ MCP Client: All {self.max_retries} attempts failed")
                    return []
        
        return []

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status from the server with retry logic.
        
        Returns:
            Dictionary with system status information
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    f"{self.server_url}/get_system_status",
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ MCP Client: Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ MCP Client: All {self.max_retries} attempts failed")
                    raise RuntimeError(f"Failed to get system status after {self.max_retries} attempts: {e}")
        
        # This should never be reached due to the raise statement above, but needed for type checking
        raise RuntimeError("Unexpected error in get_system_status")
    
    def is_available(self) -> bool:
        """Check if the MCP server is available with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(f"{self.server_url}/health", timeout=5)
                return response.status_code == 200
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ MCP Client: Health check attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        return False

# Global client instance
_mcp_client = None

def get_mcp_client() -> PassengerCommunicationsMCPClient:
    """
    Get the global MCP client instance.
    
    Returns:
        MCP client instance
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = PassengerCommunicationsMCPClient()
    return _mcp_client

def test_mcp_client():
    """Test the MCP client functionality."""
    print("🧪 Testing Passenger Communications MCP Client")
    print("=" * 60)
    
    client = PassengerCommunicationsMCPClient()
    
    # Test availability
    print("🔍 Testing server availability...")
    if client.is_available():
        print("✅ MCP server is available")
    else:
        print("❌ MCP server is not available")
        print("Note: This is expected if no MCP server is running")
        return
    
    proposals = [
        {
            "passenger_id": "PAX001",
            "passenger_name": "Alice Johnson",
            "original_flight": "UA100",
            "rebooked_flight": "UA200",
            "departure_location": "JFK",
            "arrival_location": "ORD",
            "message_content": "Your flight has been cancelled due to weather."
        },
        {
            "passenger_id": "PAX002",
            "passenger_name": "Bob Smith",
            "original_flight": "UA101",
            "rebooked_flight": "UA201",
            "departure_location": "LAX",
            "arrival_location": "JFK",
            "message_content": "Your flight has been delayed by 2 hours."
        }
    ]
    
    message_ids = []
    
    # Send proposals
    for proposal in proposals:
        try:
            result = client.send_rebooking_proposal(proposal)
            message_ids.append(result["message_id"])
            print(f"📨 Sent proposal for {proposal['passenger_name']} (ID: {result['message_id']})")
        except Exception as e:
            print(f"❌ Failed to send proposal for {proposal['passenger_name']}: {e}")
    
    # Get responses
    print("\n⏳ Getting responses...")
    for i, message_id in enumerate(message_ids):
        response = client.get_passenger_response(message_id)
        if response:
            print(f"📤 {response['passenger_name']}: {response['response']} (took {response['response_time']:.1f}s)")
        else:
            print(f"❌ No response for {proposals[i]['passenger_name']}")
    
    # Show status
    try:
        status = client.get_system_status()
        print(f"\n📊 Final Status:")
        print(f"   Queue size: {status['queue_size']}")
        print(f"   Active messages: {status['active_messages']}")
        print(f"   Messages processed: {status['stats']['messages_processed']}")
    except Exception as e:
        print(f"\n❌ Failed to get system status: {e}")

if __name__ == "__main__":
    test_mcp_client() 