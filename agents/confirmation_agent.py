import random
from typing import Dict, Any, List
import pandas as pd
from services.passenger_communications_mcp_client import get_mcp_client
import time

# Global MCP client instance
_mcp_client = None

def get_mcp_client_instance():
    """Get or create the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = get_mcp_client()  # Uses retry logic instead of mock
    return _mcp_client

def confirmation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Confirmation Agent that sends rebooking proposals and processes responses in batches.
    
    Workflow:
    1. Send all proposals to passenger communications system
    2. Collect responses in batches
    3. Return confirmations for database updates
    """
    print("🧑‍💻 ConfirmationAgent activated")

    if "rebooking_proposals" not in state:
        print("No rebooking proposals to process.")
        return state

    proposals = state["rebooking_proposals"]
    mcp_client = get_mcp_client_instance()
    
    # Step 1: Send all proposals if not already sent
    if "sent_messages" not in state:
        print(f"📨 Sending {len(proposals)} rebooking proposals to passenger communications system...")
        sent_messages = []
        
        # Clear any previous responses to avoid message ID conflicts
        try:
            # Get and discard any existing responses to start fresh
            existing_responses = mcp_client.get_all_available_responses()
            if existing_responses:
                print(f"🧹 Cleared {len(existing_responses)} previous responses to avoid conflicts")
        except Exception as e:
            print(f"⚠️ Could not clear previous responses: {e}")
        
        # Send all proposals in a batch (no individual delays)
        for i, proposal in enumerate(proposals):
            if proposal.get("assignment_successful"):
                passenger_id = proposal["passenger_id"]
                passenger_name = proposal.get("passenger_name", passenger_id)
                original_flight = proposal["original_flight"]
                departure_location = proposal.get("departure_location", "N/A")
                arrival_location = proposal["arrival_location"]
                rebooked_flight = proposal["rebooked_flight"]

                message = (
                    f"Hello {passenger_name}, your flight {original_flight} from {departure_location} to {arrival_location} has been cancelled. "
                    f"The next available flight is {rebooked_flight}. "
                    "Would you like to confirm this rebooking or contact a United Airlines representative to review other options?"
                )

                # Create proposal for MCP client
                passenger_proposal = {
                    "passenger_id": passenger_id,
                    "passenger_name": passenger_name,
                    "original_flight": original_flight,
                    "rebooked_flight": rebooked_flight,
                    "departure_location": departure_location,
                    "arrival_location": arrival_location,
                    "message_content": message
                }

                # Send to MCP server via client (no delays)
                result = mcp_client.send_rebooking_proposal(passenger_proposal)
                message_id = result["message_id"]
                
                # Only print every 10th message to reduce console spam
                if i % 10 == 0 or i == len(proposals) - 1:
                    print(f"  - Sent to {passenger_name}: ... cancelled. New flight: {rebooked_flight}. Confirm?")
                    print(f"  - MCP Message ID: {message_id[:8]}... (queued for processing)")
                
                # Track sent message for response handling
                sent_messages.append({
                    "message_id": message_id,
                    "proposal": proposal,
                    "passenger_name": passenger_name,
                    "original_flight": original_flight,
                    "rebooked_flight": rebooked_flight,
                    "sent_time": time.time(),
                    "status": "sent"
                })

        # Store sent messages in state
        state["sent_messages"] = sent_messages
        state["messages_sent_count"] = len(sent_messages)
        state["batch_size"] = 5  # Process 5 responses at a time
        state["current_batch"] = []
        state["processed_count"] = 0
        state["all_responses_processed"] = False
        
        if "messages" not in state:
            state["messages"] = []
        state["messages"].append(f"ConfirmationAgent sent {len(sent_messages)} proposals to passenger communications system")
        
        print(f"✅ Sent {len(sent_messages)} proposals in batch. Starting response collection...")
        return state
    
    # Step 2: Collect responses in batches
    sent_messages = state["sent_messages"]
    batch_size = state.get("batch_size", 5)
    current_batch = state.get("current_batch", [])
    processed_count = state.get("processed_count", 0)
    
    print(f"🔄 Collecting responses (batch size: {batch_size})")
    print(f"📊 Status: {processed_count}/{len(sent_messages)} processed")
    
    # Get all available responses from MCP server
    available_responses = mcp_client.get_all_available_responses()
    
    if available_responses:
        print(f"📦 Received {len(available_responses)} available responses")
        
        # Process each available response
        for response_data in available_responses:
            message_id = response_data["message_id"]
            passenger_name = response_data["passenger_name"]
            response = response_data["response"]
            response_time = response_data["response_time"]
            
            # Find the corresponding sent message
            matching_message = None
            for message_info in sent_messages:
                if message_info["message_id"] == message_id and message_info["status"] == "sent":
                    matching_message = message_info
                    break
            
            if matching_message:
                original_flight = matching_message["original_flight"]
                rebooked_flight = matching_message["rebooked_flight"]
                
                print(f"  ✅ {passenger_name}: {response} (took {response_time:.1f}s)")
                
                # If passenger declines, mark for manual rebooking
                if response == "manually rebook with agent":
                    rebooked_flight = f"UNASSIGNED (cancelled flight {original_flight})"
                
                # Create confirmation record
                confirmation = {
                    "passenger_id": matching_message["proposal"]["passenger_id"],
                    "passenger_name": passenger_name,
                    "original_flight": original_flight,
                    "rebooked_flight": rebooked_flight,
                    "response": response,
                    "response_time": response_time,
                    "communication_method": "MCP",
                    "processed_at": time.time()
                }
                
                current_batch.append(confirmation)
                
                # Mark message as processed
                matching_message["status"] = "completed"
                matching_message["response"] = response
                matching_message["response_time"] = response_time
                processed_count += 1
            else:
                print(f"  ⚠️  Received response for unknown message: {message_id[:8]}...")
    
    # Update state
    state["current_batch"] = current_batch
    state["processed_count"] = processed_count
    
    # Check if we have a full batch or all responses processed
    if len(current_batch) >= batch_size:
        print(f"📦 Batch complete! Collected {len(current_batch)} responses")
        state["batch_ready"] = True
        state["messages"].append(f"ConfirmationAgent collected batch of {len(current_batch)} responses")
        return state
    
    elif processed_count >= len(sent_messages):
        # All responses processed, send final batch if any
        if current_batch:
            print(f"📦 Final batch! Collected {len(current_batch)} responses")
            state["batch_ready"] = True
            state["messages"].append(f"ConfirmationAgent collected final batch of {len(current_batch)} responses")
        else:
            print("✅ All responses processed! No more batches needed.")
            state["all_responses_processed"] = True
            state["messages"].append("ConfirmationAgent completed all response processing")
        return state
    
    else:
        # Still waiting for more responses - but if we have some responses, process them
        if current_batch:
            print(f"📦 Partial batch ready! Collected {len(current_batch)} responses")
            state["batch_ready"] = True
            state["messages"].append(f"ConfirmationAgent collected partial batch of {len(current_batch)} responses")
            return state
        else:
            print(f"⏳ Waiting for more responses... ({processed_count}/{len(sent_messages)} processed)")
            return state

def test_confirmation_agent():
    """
    Test function for the confirmation agent with batch processing.
    """
    print("\nTesting confirmation agent functionality with batch processing...")

    # Sample state from passenger_rebooking_agent
    sample_state = {
        "rebooking_proposals": [
            {
                "passenger_id": "PAX001",
                "passenger_name": "John Doe",
                "original_flight": "UA100",
                "departure_location": "JFK",
                "arrival_location": "ORD",
                "rebooked_flight": "UA200",
                "assignment_successful": True,
            },
            {
                "passenger_id": "PAX002",
                "passenger_name": "Jane Smith",
                "original_flight": "UA100",
                "departure_location": "JFK",
                "arrival_location": "ORD",
                "rebooked_flight": "UA201",
                "assignment_successful": True
            },
            {
                "passenger_id": "PAX003",
                "passenger_name": "Bob Wilson",
                "original_flight": "UA100",
                "departure_location": "JFK",
                "arrival_location": "ORD",
                "rebooked_flight": "UA202",
                "assignment_successful": True
            },
            {
                "passenger_id": "PAX004",
                "passenger_name": "Alice Johnson",
                "original_flight": "UA100",
                "departure_location": "JFK",
                "arrival_location": "ORD",
                "rebooked_flight": "UA203",
                "assignment_successful": True
            },
            {
                "passenger_id": "PAX005",
                "passenger_name": "Charlie Brown",
                "original_flight": "UA100",
                "departure_location": "JFK",
                "arrival_location": "ORD",
                "rebooked_flight": "UA204",
                "assignment_successful": True
            },
            {
                "passenger_id": "PAX006",
                "original_flight": "UA100",
                "departure_location": "JFK",
                "arrival_location": "ORD",
                "rebooked_flight": "NO_FLIGHT_AVAILABLE",
                "assignment_successful": False
            }
        ],
        "messages": []
    }

    # Step 1: Send all proposals
    result_state = confirmation_agent(sample_state)
    print(f"\n📊 After sending proposals:")
    print(f"  Messages sent: {result_state.get('messages_sent_count', 0)}")
    print(f"  Sent messages: {len(result_state.get('sent_messages', []))}")
    
    # Step 2: Simulate batch processing
    print(f"\n🔄 Simulating batch processing...")
    batch_count = 0
    
    while not result_state.get('all_responses_processed', False):
        batch_count += 1
        print(f"\n--- Batch #{batch_count} ---")
        result_state = confirmation_agent(result_state)
        
        if result_state.get('batch_ready'):
            batch = result_state.get('current_batch', [])
            print(f"📦 Batch ready with {len(batch)} responses:")
            for conf in batch:
                print(f"  - {conf['passenger_name']}: {conf['response']}")
            
            # Simulate sending to rebooking agent and clearing batch
            result_state["current_batch"] = []
            result_state["batch_ready"] = False
            result_state["messages"].append(f"Batch #{batch_count} sent to rebooking agent")
        
        # Remove or set to zero any sleep in the polling loop
        # (No sleep for fastest response collection)
    
    # Final results
    print(f"\n📊 Final Results:")
    print(f"  Total batches processed: {batch_count}")
    print(f"  Total responses processed: {result_state.get('processed_count', 0)}")
    
    if result_state.get('messages'):
        print("\n📝 Agent Messages:")
        for msg in result_state['messages']:
            print(f"  - {msg}")

if __name__ == "__main__":
    test_confirmation_agent() 