import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import pandas as pd
from typing import TypedDict, List, Any, Dict, NotRequired
from dotenv import load_dotenv

# Load environment variables (including API key)
load_dotenv()

# Import agent functions
from agents.llm_passenger_rebooking_agent import llm_passenger_rebooking_agent
from agents.confirmation_agent import confirmation_agent

# Import LangGraph components
from langgraph.graph import StateGraph, END

# Define the state for the graph
class SystemState(TypedDict):
    proposals: NotRequired[List[Dict[str, Any]]]
    messages: List[str]
    flight_cancellation_notification: NotRequired[Dict[str, Any]]
    impacted_passengers: NotRequired[List[Dict[str, Any]]]  # Changed from pd.DataFrame to List[Dict]
    alternative_flights: NotRequired[List[Dict[str, Any]]]  # Changed from pd.DataFrame to List[Dict]
    rebooking_proposals: NotRequired[List[Dict[str, Any]]]
    confirmations: NotRequired[List[Dict[str, Any]]]
    assignment_summary: NotRequired[Dict[str, Any]]
    confirmations_for_verification: NotRequired[List[Dict[str, Any]]]
    # Confirmation agent state fields
    sent_messages: NotRequired[List[Dict[str, Any]]]
    current_batch: NotRequired[List[Dict[str, Any]]]
    batch_ready: NotRequired[bool]
    all_responses_processed: NotRequired[bool]

def run_end_to_end_test_with_langgraph():
    """
    Runs an end-to-end test of the LLM-powered passenger rebooking and confirmation workflow using LangGraph.
    """
    print("🚀 Starting end-to-end test for LLM-powered passenger rebooking workflow with LangGraph...")

    # Define the nodes for the graph
    def propose_rebooking_node(state: SystemState) -> SystemState:
        print("\n--- Step 1: LLM Agent Generating Rebooking Proposals ---")
        return llm_passenger_rebooking_agent(state, db_path="../database/united_ops.db") # type: ignore

    def confirmation_node(state: SystemState) -> SystemState:
        print("\n--- Step 2: Collecting Passenger Confirmations ---")
        
        # Loop until all responses are collected
        while not state.get("all_responses_processed", False):
            state = confirmation_agent(state)  # type: ignore
            
            # If we have a batch ready, process it
            if state.get("batch_ready"):
                batch = state.get("current_batch", [])
                print(f"📦 Processing batch of {len(batch)} confirmations")
                
                # Add batch to confirmations list
                if "confirmations" not in state:
                    state["confirmations"] = []
                state["confirmations"].extend(batch)
                
                # Clear the batch and continue collecting
                state["current_batch"] = []
                state["batch_ready"] = False
        
        print(f"✅ All confirmations collected: {len(state.get('confirmations', []))}")
        return state

    def update_db_node(state: SystemState) -> SystemState:
        print("\n--- Step 3: Updating Passenger Records in Database ---")
        # The llm_passenger_rebooking_agent will POP 'confirmations', so we save them for verification
        confirmations_to_verify = state.get("confirmations", [])
        new_state = llm_passenger_rebooking_agent(state, db_path="../database/united_ops.db") # type: ignore
        new_state["confirmations_for_verification"] = confirmations_to_verify
        return new_state # type: ignore

    # Create the graph
    workflow = StateGraph(SystemState)

    # Add nodes to the graph
    workflow.add_node("propose_rebooking", propose_rebooking_node)
    workflow.add_node("get_confirmations", confirmation_node)
    workflow.add_node("update_database", update_db_node)

    # Add edges to define the flow
    workflow.set_entry_point("propose_rebooking")
    workflow.add_edge("propose_rebooking", "get_confirmations")
    workflow.add_edge("get_confirmations", "update_database")
    workflow.add_edge("update_database", END)

    # Compile the graph into a runnable app
    app = workflow.compile()

    # Define the initial state for the test
    initial_state = {
        "proposals": [],
        "messages": [],
        "flight_cancellation_notification": {
            "flight_number": "DL7016",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        }
    }

    # Invoke the graph with the initial state
    final_state = app.invoke(initial_state)

    # Verification Step
    print("\n--- Step 4: Verifying Database Updates ---")
    confirmations = final_state.get("confirmations_for_verification", [])
    accepted_confirmations = [c for c in confirmations if c['response'] == 'accept rebooking']
    
    if not accepted_confirmations:
        print("No passengers accepted the rebooking. Verification cannot proceed.")
        return
        
    # Fix database path for verification
    db_path = "../database/united_ops.db"  # Relative path from agents directory
    if not os.path.isabs(db_path):
        # Convert relative path to absolute path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, db_path)
    
    print(f"📁 Using database path for verification: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        passenger_ids = [c['passenger_id'] for c in accepted_confirmations]
        query = "SELECT passenger_id, flight_number FROM passengers WHERE passenger_id IN ({})".format(
            ",".join(["?"] * len(passenger_ids))
        )
        updated_passengers_df = pd.read_sql_query(query, conn, params=passenger_ids)
        
        print("Verifying passenger records in the database for those who accepted:")
        
        verification_summary = []
        for conf in accepted_confirmations:
            passenger_id = conf['passenger_id']
            expected_flight = conf['rebooked_flight']
            
            # Filter the DataFrame for this passenger
            passenger_data = updated_passengers_df[updated_passengers_df['passenger_id'] == passenger_id]
            
            if len(passenger_data) > 0:
                actual_flight = passenger_data.iloc[0]['flight_number']
                status = "✅ MATCH" if actual_flight == expected_flight else f"❌ MISMATCH (Expected: {expected_flight}, Got: {actual_flight})"
            else:
                actual_flight = "Not Found"
                status = "❌ NOT FOUND"

            verification_summary.append({
                "passenger_id": passenger_id,
                "expected_flight": expected_flight,
                "actual_flight": actual_flight,
                "status": status
            })

        verification_df = pd.DataFrame(verification_summary)
        print(verification_df)
        
        mismatch_count = len(verification_df[verification_df['status'].str.contains("MISMATCH")])
        not_found_count = len(verification_df[verification_df['status'].str.contains("NOT FOUND")])

        if mismatch_count == 0 and not_found_count == 0:
            print("\n🎉 End-to-end test PASSED! All records verified.")
        else:
            print(f"\n❌ End-to-end test FAILED! Found {mismatch_count} mismatches and {not_found_count} missing records.")

    except Exception as e:
        print(f"An error occurred during verification: {e}")
    finally:
        conn.close()

def run_simple_end_to_end_test():
    """
    Runs a simpler end-to-end test without LangGraph for easier debugging.
    """
    print("🚀 Starting simple end-to-end test for LLM-powered passenger rebooking workflow...")
    
    # Define the initial state for the test
    initial_state = {
        "proposals": [],
        "messages": [],
        "flight_cancellation_notification": {
            "flight_number": "DL7016",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        }
    }

    print("\n--- Step 1: LLM Agent Generating Rebooking Proposals ---")
    state_after_rebooking = llm_passenger_rebooking_agent(initial_state)
    
    print(f"📊 Rebooking Results:")
    print(f"  - Impacted passengers: {len(state_after_rebooking.get('impacted_passengers', []))}")
    print(f"  - Alternative flights: {len(state_after_rebooking.get('alternative_flights', []))}")
    print(f"  - Rebooking proposals: {len(state_after_rebooking.get('rebooking_proposals', []))}")
    
    if state_after_rebooking.get('llm_analysis'):
        print(f"  - LLM Analysis: {state_after_rebooking['llm_analysis'][:200]}...")

    print("\n--- Step 2: Simulating Passenger Confirmations ---")
    state_after_confirmations = confirmation_agent(state_after_rebooking)
    
    print(f"📊 Confirmation Results:")
    print(f"  - Confirmations processed: {len(state_after_confirmations.get('confirmations', []))}")
    
    if state_after_confirmations.get('confirmations'):
        accepted = [c for c in state_after_confirmations['confirmations'] if c['response'] == 'accept rebooking']
        print(f"  - Accepted rebookings: {len(accepted)}")
        print(f"  - Declined rebookings: {len(state_after_confirmations['confirmations']) - len(accepted)}")

    print("\n--- Step 3: Updating Passenger Records in Database ---")
    final_state = llm_passenger_rebooking_agent(state_after_confirmations)
    
    print("✅ End-to-end test completed!")
    print(f"📊 Final Results:")
    print(f"  - Total messages: {len(final_state.get('messages', []))}")
    print(f"  - Final proposals: {len(final_state.get('proposals', []))}")
    
    return final_state

if __name__ == "__main__":
    # Debug: Check if API key is loaded
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    else:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
    
    # Run the simple test first for easier debugging
    #print("=" * 60)
    #print("SIMPLE END-TO-END TEST")
    #print("=" * 60)
    #run_simple_end_to_end_test()
    
    print("\n" + "=" * 60)
    print("LANGGRAPH END-TO-END TEST")
    print("=" * 60)
    run_end_to_end_test_with_langgraph() 