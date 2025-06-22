import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import TypedDict, List, Any, Dict, NotRequired
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables (including API key)
load_dotenv()

# Import agent functions
from agents.crew_ops_agent import crew_ops_agent
from agents.dispatch_ops_agent import dispatch_ops_agent
from agents.planner_agent import planner_agent
from agents.llm_passenger_rebooking_agent import llm_passenger_rebooking_agent
from agents.confirmation_agent import confirmation_agent

# Import LangGraph components
from langgraph.graph import StateGraph, END

# Define the state for the multi-agent workflow
class MultiAgentState(TypedDict):
    proposals: NotRequired[List[Dict[str, Any]]]
    messages: List[str]
    crew_schedule: NotRequired[pd.DataFrame]
    passenger_itinerary: NotRequired[pd.DataFrame]
    legality_flags: NotRequired[List[str]]
    crew_substitutions: NotRequired[Dict[str, List[str]]]
    current_flight_crews: NotRequired[Dict[str, List[str]]]
    iteration_count: NotRequired[int]
    plan_summary: NotRequired[str]
    final_plan: NotRequired[Dict[str, Any]]
    rebooking_proposals: NotRequired[List[Dict[str, Any]]]
    # Dispatch ops fields
    weather_data: NotRequired[Dict[str, Any]]
    fuel_data: NotRequired[Dict[str, Any]]
    crew_legality_status: NotRequired[str]
    weather_status: NotRequired[str]
    fuel_status: NotRequired[str]
    dispatch_status: NotRequired[str]
    dispatch_violations: NotRequired[Dict[str, Any]]
    # Passenger rebooking fields
    flight_cancellation_notification: NotRequired[Dict[str, Any]]
    impacted_passengers: NotRequired[List[Dict[str, Any]]]
    alternative_flights: NotRequired[List[Dict[str, Any]]]
    confirmations: NotRequired[List[Dict[str, Any]]]
    assignment_summary: NotRequired[Dict[str, Any]]
    # Confirmation agent fields
    sent_messages: NotRequired[List[Dict[str, Any]]]
    current_batch: NotRequired[List[Dict[str, Any]]]
    batch_ready: NotRequired[bool]
    all_responses_processed: NotRequired[bool]
    run_id: NotRequired[str]

def run_multi_agent_workflow_test():
    """
    Runs a comprehensive test of the multi-agent airline operations workflow.
    
    This workflow demonstrates:
    1. Crew Operations Agent - FAA compliance and crew substitutions
    2. Dispatch Operations Agent - Dispatch readiness checks
    3. Passenger Rebooking Agent - Intelligent passenger rebooking
    4. Confirmation Agent - Passenger communication and confirmations
    5. Planner Agent - Executive summary and coordination
    """
    print("🚀 Starting Multi-Agent Airline Operations Workflow Test...")
    print("=" * 80)

    # Define the nodes for the graph
    def crew_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- Step 1: Crew Operations Agent (FAA Compliance) ---")
        return crew_ops_agent(state)

    def dispatch_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- Step 2: Dispatch Operations Agent (Readiness Check) ---")
        return dispatch_ops_agent(state)

    def passenger_rebooking_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- Step 3: Passenger Rebooking Agent (Intelligent Rebooking) ---")
        return llm_passenger_rebooking_agent(state)

    def confirmation_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- Step 4: Confirmation Agent (Passenger Communications) ---")
        
        # Loop until all responses are collected
        loop_count = 0
        max_loops = 10  # Prevent infinite loops
        
        while not state.get("all_responses_processed", False) and loop_count < max_loops:
            loop_count += 1
            state = confirmation_agent(state)
            
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
        
        if loop_count >= max_loops:
            print(f"⚠️ Reached maximum loops ({max_loops}) - forcing completion")
            state["all_responses_processed"] = True
            state["messages"] = state.get("messages", []) + [f"WARNING: Reached maximum confirmation loops ({max_loops})"]
        
        print(f"✅ All confirmations collected: {len(state.get('confirmations', []))}")
        return state

    def database_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- Step 5: Database Update (Passenger Records) ---")
        # Route back to rebooking agent to handle database updates
        return llm_passenger_rebooking_agent(state)

    def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- Step 6: Planner Agent (Executive Summary) ---")
        run_id = state.get("run_id", f"multi-agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        return planner_agent(state, run_id=run_id)

    # Create the graph
    workflow = StateGraph(MultiAgentState)

    # Add nodes to the graph
    workflow.add_node("crew_ops", crew_ops_node)
    workflow.add_node("dispatch_ops", dispatch_ops_node)
    workflow.add_node("passenger_rebooking", passenger_rebooking_node)
    workflow.add_node("confirmation", confirmation_node)
    workflow.add_node("database_update", database_update_node)
    workflow.add_node("planner", planner_node)

    # Add edges to define the flow
    workflow.set_entry_point("crew_ops")
    workflow.add_edge("crew_ops", "dispatch_ops")
    workflow.add_edge("dispatch_ops", "passenger_rebooking")
    workflow.add_edge("passenger_rebooking", "confirmation")
    workflow.add_edge("confirmation", "database_update")
    workflow.add_edge("database_update", "planner")
    workflow.add_edge("planner", END)

    # Compile the graph into a runnable app
    app = workflow.compile()

    # Define the initial state for the test
    run_id = f"multi-agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    initial_state = {
        "run_id": run_id,  # Add run_id to initial state
        "proposals": [],
        "messages": [],
        "weather_data": {
            "DepartureWeather": ["SKC"]  # Clear skies
        },
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"  # Fueled
        },
        "flight_cancellation_notification": {
            "flight_number": "UA70161",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        }
    }

    # Invoke the graph with the initial state
    final_state = app.invoke(initial_state)

    # Print comprehensive results
    print("\n" + "=" * 80)
    print("📊 MULTI-AGENT WORKFLOW RESULTS")
    print("=" * 80)
    
    print(f"\n🛰️ Dispatch Status: {final_state.get('dispatch_status', 'UNKNOWN')}")
    print(f"   Crew Legality: {final_state.get('crew_legality_status', 'UNKNOWN')}")
    print(f"   Weather Status: {final_state.get('weather_status', 'UNKNOWN')}")
    print(f"   Fuel Status: {final_state.get('fuel_status', 'UNKNOWN')}")
    
    if final_state.get('dispatch_violations'):
        print(f"   Violations: {final_state.get('dispatch_violations')}")
    
    print(f"\n👥 Passenger Rebooking:")
    print(f"   Impacted passengers: {len(final_state.get('impacted_passengers', []))}")
    print(f"   Alternative flights: {len(final_state.get('alternative_flights', []))}")
    print(f"   Rebooking proposals: {len(final_state.get('rebooking_proposals', []))}")
    print(f"   Confirmations: {len(final_state.get('confirmations', []))}")
    
    print(f"\n🧑‍✈️ Crew Operations:")
    print(f"   Crew substitutions: {len(final_state.get('crew_substitutions', {}))}")
    print(f"   Legality flags: {len(final_state.get('legality_flags', []))}")
    
    print(f"\n📝 System Messages ({len(final_state.get('messages', []))}):")
    for msg in final_state.get('messages', [])[-5:]:  # Show last 5 messages
        print(f"   - {msg}")
    
    if final_state.get('plan_summary'):
        print(f"\n📋 Executive Summary Preview:")
        summary = final_state['plan_summary'][:200] + "..." if len(final_state['plan_summary']) > 200 else final_state['plan_summary']
        print(f"   {summary}")
    
    print(f"\n✅ Multi-agent workflow test completed!")
    return final_state

def run_simple_multi_agent_test():
    """
    Runs a simpler multi-agent test without LangGraph for easier debugging.
    """
    print("🚀 Starting simple multi-agent test...")
    
    # Define the initial state for the test
    initial_state = {
        "proposals": [],
        "messages": [],
        "weather_data": {
            "DepartureWeather": ["SKC"]  # Clear skies
        },
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"  # Fueled
        },
        "flight_cancellation_notification": {
            "flight_number": "UA70161",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        }
    }

    print("\n--- Step 1: Crew Operations Agent ---")
    state_after_crew = crew_ops_agent(initial_state)
    print(f"  Crew substitutions: {len(state_after_crew.get('crew_substitutions', {}))}")

    print("\n--- Step 2: Dispatch Operations Agent ---")
    state_after_dispatch = dispatch_ops_agent(state_after_crew)
    print(f"  Dispatch status: {state_after_dispatch.get('dispatch_status')}")

    print("\n--- Step 3: Passenger Rebooking Agent ---")
    state_after_rebooking = llm_passenger_rebooking_agent(state_after_dispatch)
    print(f"  Rebooking proposals: {len(state_after_rebooking.get('rebooking_proposals', []))}")

    print("\n--- Step 4: Confirmation Agent ---")
    state_after_confirmation = confirmation_agent(state_after_rebooking)
    print(f"  Confirmations: {len(state_after_confirmation.get('confirmations', []))}")

    print("\n--- Step 5: Database Update ---")
    state_after_db_update = llm_passenger_rebooking_agent(state_after_confirmation)
    print(f"  Database updates: {len(state_after_db_update.get('messages', []))}")

    print("\n--- Step 6: Planner Agent ---")
    final_state = planner_agent(state_after_db_update, run_id="simple-test")
    print(f"  Plan summary generated: {bool(final_state.get('plan_summary'))}")

    print("\n✅ Simple multi-agent test completed!")
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
    #print("SIMPLE MULTI-AGENT TEST")
    #print("=" * 60)
    #run_simple_multi_agent_test()
    
    print("\n" + "=" * 60)
    print("LANGGRAPH MULTI-AGENT WORKFLOW TEST")
    print("=" * 60)
    run_multi_agent_workflow_test() 