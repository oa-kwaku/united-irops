"""
Passenger Communications MCP Server

This is an MCP server that simulates a passenger communications application.
It can be called by the confirmation agent via MCP to send rebooking proposals
and receive passenger responses.
"""

import json
import logging
import random
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from queue import Queue, Empty
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PassengerMessage:
    message_id: str
    passenger_id: str
    passenger_name: str
    original_flight: str
    rebooked_flight: str
    departure_location: str
    arrival_location: str
    message_content: str
    timestamp: float
    status: str = "pending"
    response: Optional[str] = None
    response_timestamp: Optional[float] = None

class PassengerCommunicationsMCP:
    """
    MCP-compatible passenger communications system.
    This simulates a real passenger communications application.
    """
    
    def __init__(self, response_delay_range: tuple = (1, 10)):
        self.response_delay_range = response_delay_range
        self.message_queue = Queue()
        self.running = False
        self.processing_thread = None
        self.active_messages: Dict[str, PassengerMessage] = {}
        
        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_processed': 0,
            'accept_count': 0,
            'decline_count': 0
        }
    
    def start(self):
        """Start the passenger communications system."""
        if self.running:
            logger.warning("System is already running")
            return
        
        self.running = True
        logger.info("🚀 Starting Passenger Communications MCP System")
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_messages_loop, daemon=True)
        self.processing_thread.start()
        
        logger.info("✅ System started successfully")
    
    def stop(self):
        """Stop the passenger communications system."""
        if not self.running:
            logger.warning("System is not running")
            return
        
        self.running = False
        logger.info("🛑 Stopping Passenger Communications MCP System")
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        logger.info("✅ System stopped successfully")
        self._print_stats()
    
    def send_rebooking_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        MCP method: Send a rebooking proposal to a passenger.
        
        Args:
            proposal: Dictionary containing rebooking proposal details
            
        Returns:
            Dictionary with message_id and status
        """
        if not self.running:
            raise RuntimeError("System is not running")
        
        # Create passenger message
        message = PassengerMessage(
            message_id=str(uuid.uuid4()),
            passenger_id=proposal["passenger_id"],
            passenger_name=proposal.get("passenger_name", proposal["passenger_id"]),
            original_flight=proposal["original_flight"],
            rebooked_flight=proposal["rebooked_flight"],
            departure_location=proposal.get("departure_location", "N/A"),
            arrival_location=proposal["arrival_location"],
            message_content=proposal.get("message_content", ""),
            timestamp=time.time()
        )
        
        # Add to queue
        self.message_queue.put(message)
        self.active_messages[message.message_id] = message
        self.stats['messages_received'] += 1
        
        logger.info(f"📨 MCP: Received proposal for {message.passenger_name} (ID: {message.message_id[:8]}...)")
        logger.info(f"   Queue size: {self.message_queue.qsize()}")
        
        return {
            "message_id": message.message_id,
            "status": "queued",
            "passenger_name": message.passenger_name,
            "queue_position": self.message_queue.qsize()
        }
    
    def get_passenger_response(self, message_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        MCP method: Get response for a specific message ID.
        
        Args:
            message_id: ID of the message to get response for
            timeout: Timeout in seconds
            
        Returns:
            Response dictionary or None if not available
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if message_id in self.active_messages:
                message = self.active_messages[message_id]
                if message.status == "completed" and message.response is not None and message.response_timestamp is not None:
                    # Remove from active messages
                    del self.active_messages[message_id]
                    
                    response_data = {
                        "message_id": message.message_id,
                        "passenger_id": message.passenger_id,
                        "passenger_name": message.passenger_name,
                        "response": message.response,
                        "response_time": message.response_timestamp - message.timestamp,
                        "original_flight": message.original_flight,
                        "rebooked_flight": message.rebooked_flight,
                        "status": "completed"
                    }
                    
                    logger.info(f"📤 MCP: Returning response for {message.passenger_name}: {message.response}")
                    return response_data
            
            time.sleep(0.1)
        
        logger.warning(f"⏰ MCP: Timeout waiting for response to message {message_id}")
        return None
    
    def get_all_available_responses(self) -> List[Dict[str, Any]]:
        """
        MCP method: Get all available responses that are ready.
        
        Returns:
            List of response dictionaries for completed messages
        """
        available_responses = []
        completed_message_ids = []
        
        # Check all active messages for completed ones
        for message_id, message in self.active_messages.items():
            if message.status == "completed" and message.response is not None and message.response_timestamp is not None:
                response_data = {
                    "message_id": message.message_id,
                    "passenger_id": message.passenger_id,
                    "passenger_name": message.passenger_name,
                    "response": message.response,
                    "response_time": message.response_timestamp - message.timestamp,
                    "original_flight": message.original_flight,
                    "rebooked_flight": message.rebooked_flight,
                    "status": "completed"
                }
                available_responses.append(response_data)
                completed_message_ids.append(message_id)
        
        # Remove completed messages from active messages
        for message_id in completed_message_ids:
            del self.active_messages[message_id]
        
        if available_responses:
            logger.info(f"📤 MCP: Returning {len(available_responses)} available responses")
        
        return available_responses

    def get_system_status(self) -> Dict[str, Any]:
        """
        MCP method: Get current system status.
        
        Returns:
            Dictionary with system status information
        """
        return {
            "running": self.running,
            "queue_size": self.message_queue.qsize(),
            "active_messages": len(self.active_messages),
            "stats": self.stats.copy()
        }
    
    def _process_messages_loop(self):
        """Main loop for processing messages from the queue."""
        logger.info("🔄 Starting message processing loop")
        
        while self.running:
            try:
                # Check if there are messages in the queue
                if not self.message_queue.empty():
                    # Get all messages from the queue
                    messages = []
                    while not self.message_queue.empty():
                        try:
                            message = self.message_queue.get_nowait()
                            messages.append(message)
                        except Empty:
                            break
                    
                    # Randomly select a message to process
                    if messages:
                        selected_message = random.choice(messages)
                        logger.info(f"🎲 Randomly selected message for {selected_message.passenger_name} from {len(messages)} available messages")
                        
                        # Put the other messages back in the queue
                        for message in messages:
                            if message.message_id != selected_message.message_id:
                                self.message_queue.put(message)
                        
                        # Process the selected message
                        self._process_single_message(selected_message)
                
                # Wait a bit before checking again
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Error in message processing loop: {e}")
                continue
        
        logger.info("🔄 Message processing loop stopped")
    
    def _process_single_message(self, message: PassengerMessage):
        """Process a single message with realistic passenger response logic."""
        logger.info(f"⏳ Processing message for {message.passenger_name} (ID: {message.message_id[:8]}...)")
        
        # Update status
        message.status = "processing"
        
        # Simulate passenger thinking time
        delay = random.uniform(*self.response_delay_range)
        logger.info(f"   Passenger {message.passenger_name} thinking for {delay:.1f} seconds...")
        time.sleep(delay)
        
        # Generate passenger response
        response = self._generate_passenger_response(message)
        message.response = response
        message.status = "completed"
        message.response_timestamp = time.time()
        
        # Update statistics
        self.stats['messages_processed'] += 1
        if response == "accept rebooking":
            self.stats['accept_count'] += 1
        else:
            self.stats['decline_count'] += 1
        
        logger.info(f"   {message.passenger_name} decided: {response}")
    
    def _generate_passenger_response(self, message: PassengerMessage) -> str:
        """
        Generate a realistic passenger response based on message content.
        Same logic as before but isolated in this application.
        """
        message_lower = message.message_content.lower() if message.message_content else ""
        
        # If message mentions cancellation, passengers are more likely to accept rebooking
        if "cancelled" in message_lower or "cancellation" in message_lower:
            if random.random() < 0.8:
                return "accept rebooking"
            else:
                return "manually rebook with agent"
        
        # If message mentions delay, passengers are more likely to want alternatives
        elif "delayed" in message_lower or "delay" in message_lower:
            if random.random() < 0.6:
                return "accept rebooking"
            else:
                return "manually rebook with agent"
        
        # Default behavior - 75% accept, 25% want manual rebooking
        else:
            if random.random() < 0.75:
                return "accept rebooking"
            else:
                return "manually rebook with agent"
    
    def _print_stats(self):
        """Print system statistics."""
        logger.info("📊 System Statistics:")
        logger.info(f"   Messages received: {self.stats['messages_received']}")
        logger.info(f"   Messages processed: {self.stats['messages_processed']}")
        logger.info(f"   Acceptances: {self.stats['accept_count']}")
        logger.info(f"   Declines: {self.stats['decline_count']}")
        
        if self.stats['messages_processed'] > 0:
            accept_rate = (self.stats['accept_count'] / self.stats['messages_processed']) * 100
            logger.info(f"   Acceptance rate: {accept_rate:.1f}%")

# Global instance
_passenger_mcp = None

def get_passenger_mcp() -> PassengerCommunicationsMCP:
    """Get the global passenger MCP instance."""
    global _passenger_mcp
    if _passenger_mcp is None:
        _passenger_mcp = PassengerCommunicationsMCP()
    return _passenger_mcp

def start_passenger_mcp():
    """Start the global passenger MCP system."""
    mcp = get_passenger_mcp()
    mcp.start()

def stop_passenger_mcp():
    """Stop the global passenger MCP system."""
    global _passenger_mcp
    if _passenger_mcp:
        _passenger_mcp.stop()
        _passenger_mcp = None

def test_mcp_system():
    """Test the MCP passenger communications system."""
    print("🧪 Testing Passenger Communications MCP System")
    print("=" * 60)
    
    # Start the system
    mcp = PassengerCommunicationsMCP(response_delay_range=(1, 3))
    mcp.start()
    
    try:
        # Send multiple proposals
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
            },
            {
                "passenger_id": "PAX003",
                "passenger_name": "Carol Davis",
                "original_flight": "UA102",
                "rebooked_flight": "UA202",
                "departure_location": "ORD",
                "arrival_location": "LAX",
                "message_content": "We have a new flight option available for you."
            }
        ]
        
        message_ids = []
        
        # Send all proposals via MCP
        for proposal in proposals:
            result = mcp.send_rebooking_proposal(proposal)
            message_ids.append(result["message_id"])
            print(f"📨 MCP: Sent proposal for {proposal['passenger_name']} (ID: {result['message_id'][:8]}...)")
        
        # Wait for responses
        print("\n⏳ Waiting for passenger responses...")
        
        for i, message_id in enumerate(message_ids):
            response = mcp.get_passenger_response(message_id, timeout=15)
            if response:
                print(f"📤 MCP: {response['passenger_name']}: {response['response']} (took {response['response_time']:.1f}s)")
            else:
                print(f"❌ MCP: No response received for {proposals[i]['passenger_name']}")
        
        # Show final status
        print(f"\n📊 Final MCP Status:")
        status = mcp.get_system_status()
        print(f"   Queue size: {status['queue_size']}")
        print(f"   Active messages: {status['active_messages']}")
        print(f"   Messages processed: {status['stats']['messages_processed']}")
        
    finally:
        # Stop the system
        mcp.stop()

if __name__ == "__main__":
    test_mcp_system() 