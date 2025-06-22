# United Airlines Operations Agentic System
# This file contains the graph assembly and execution code for the United Airlines multi-agent operations system

import sys
import os
# Add the parent directory to the path so we can import from agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from typing import Annotated, TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from operator import add
from datetime import datetime, timedelta

# Import the individual agents
from agents.crew_ops_agent import crew_ops_agent
from agents.dispatch_ops_agent import dispatch_ops_agent
from agents.planner_agent import planner_agent
from agents.llm_passenger_rebooking_agent import llm_passenger_rebooking_agent
from agents.confirmation_agent import confirmation_agent

# Shared agent state definition
class SystemState(TypedDict):
    proposals: Annotated[List[Dict[str, Any]], add]
    crew_schedule: pd.DataFrame
    passenger_itinerary: pd.DataFrame
    legality_flags: Annotated[List[str], add]
    crew_substitutions: Dict[str, List[str]]
    current_flight_crews: Dict[str, List[str]]
    messages: Annotated[List[str], add]
    iteration_count: int
    plan_summary: str
    final_plan: Dict[str, Any]
    rebooking_proposals: Annotated[List[Dict[str, Any]], add]
    # Additional fields for dispatch ops
    weather_data: Dict[str, Any]
    fuel_data: Dict[str, Any]
    crew_legality_status: str
    weather_status: str
    fuel_status: str
    dispatch_status: str
    dispatch_violations: Dict[str, Any]
    # Additional fields for passenger rebooking
    flight_cancellation_notification: Dict[str, Any]
    impacted_passengers: List[Dict[str, Any]]
    alternative_flights: List[Dict[str, Any]]
    confirmations: List[Dict[str, Any]]
    assignment_summary: Dict[str, Any]
    # Additional fields for confirmation agent
    sent_messages: List[Dict[str, Any]]
    current_batch: List[Dict[str, Any]]
    batch_ready: bool
    all_responses_processed: bool

# Graph Assembly
def create_multi_agent_workflow():
    """
    Creates and returns a compiled multi-agent workflow graph.
    
    The workflow includes:
    1. Crew Operations Agent - FAA compliance and crew substitutions
    2. Dispatch Operations Agent - Dispatch readiness checks
    3. Passenger Rebooking Agent - Intelligent passenger rebooking
    4. Confirmation Agent - Passenger communication and confirmations
    5. Planner Agent - Executive summary and coordination
    """
    print("🔧 Creating multi-agent workflow graph...")
    
    # Create the graph
    graph = StateGraph(SystemState)

    # Add nodes
    graph.add_node("crew_ops", crew_ops_agent)
    graph.add_node("dispatch_ops", dispatch_ops_agent)
    graph.add_node("passenger_rebooking", llm_passenger_rebooking_agent)
    graph.add_node("confirmation", confirmation_agent)
    graph.add_node("planner", planner_agent)

    # Define execution order: crew_ops -> dispatch_ops -> passenger_rebooking -> confirmation -> planner
    graph.set_entry_point("crew_ops")
    graph.add_edge("crew_ops", "dispatch_ops")
    graph.add_edge("dispatch_ops", "passenger_rebooking")
    graph.add_edge("passenger_rebooking", "confirmation")
    graph.add_edge("confirmation", "planner")
    graph.add_edge("planner", END)

    # Compile graph
    compiled_workflow = graph.compile()
    
    print("✅ Multi-agent workflow graph created successfully")
    return compiled_workflow

def create_simple_workflow():
    """
    Creates a simpler workflow with just crew ops and planner for testing.
    """
    print("🔧 Creating simple workflow graph...")
    
    # Create the graph
    workflow = StateGraph(SystemState)

    # Add nodes
    workflow.add_node("crew_ops", crew_ops_agent)
    workflow.add_node("planner", planner_agent)

    # Define flow
    workflow.set_entry_point("crew_ops")
    workflow.add_edge("crew_ops", "planner")
    workflow.add_edge("planner", END)

    # Compile graph
    compiled_workflow = workflow.compile()
    
    print("✅ Simple workflow graph created successfully")
    return compiled_workflow

def run_multi_agent_system(workflow_type: str = "full"):
    """
    Runs the multi-agent airline operations system.
    
    Args:
        workflow_type (str): Either "full" for complete workflow or "simple" for basic testing
    """
    print("🚀 Starting Multi-Agent Airline Operations Analysis...")
    print("=" * 60)

    # Create the appropriate workflow
    if workflow_type == "full":
        plan_executor = create_multi_agent_workflow()
    else:
        plan_executor = create_simple_workflow()

    # Initialize state with sample data
    initial_state = {
        "proposals": [],
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C001", "C002"],
            "assigned_flight": ["UA101", "UA101"],
            "duty_start": [(datetime.now()).isoformat(), (datetime.now()).isoformat()],
            "duty_end": [(datetime.now() + timedelta(hours=12)).isoformat(), (datetime.now() + timedelta(hours=8)).isoformat()],
            "rest_hours_prior": [8, 12],  # First crew below minimum
            "fatigue_score": [1.1, 0.3],  # First crew above maximum
            "role": ["Pilot", "Attendant"],
            "base": ["ORD", "ORD"],
            "name": ["Capt. Smith", "J. Doe"]
        }),
        "passenger_itinerary": pd.DataFrame({
            "passenger_id": ["PAX001", "PAX002"],
            "flight_number": ["UA101", "UA101"],
            "name": ["John Doe", "Jane Smith"],
            "loyalty_tier": ["Gold", "Silver"]
        }),
        "flight_crew_mapping": {},
        "crew_substitutions": {},
        "current_flight_crews": {},
        "legality_flags": [],
        "messages": [],
        "iteration_count": 0,
        "weather_data": {
            "DepartureWeather": ["TS"]  # Thunderstorm
        },
        "fuel_data": {
            "DepartureFuel": "FUEL ORDER"  # Not fueled
        },
        "flight_cancellation_notification": {
            "flight_number": "UA70161",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        }
    }

    # Execute the multi-agent system
    output = plan_executor.invoke(initial_state)

    print("=" * 60)
    print("✅ Analysis Complete!")
    print("=" * 60)
    
    # Print summary results
    print(f"\n📊 Final Results:")
    print(f"  Total messages: {len(output.get('messages', []))}")
    print(f"  Final proposals: {len(output.get('proposals', []))}")
    print(f"  Crew substitutions: {len(output.get('crew_substitutions', {}))}")
    print(f"  Dispatch status: {output.get('dispatch_status', 'UNKNOWN')}")
    print(f"  Rebooking proposals: {len(output.get('rebooking_proposals', []))}")
    print(f"  Confirmations: {len(output.get('confirmations', []))}")
    
    if output.get('plan_summary'):
        print(f"  Plan summary generated: {len(output['plan_summary'])} characters")
    
    return output

if __name__ == "__main__":
    # Run the simple workflow first for testing
    print("Testing simple workflow...")
    run_multi_agent_system("simple")
    
    # Uncomment to run the full workflow
    # print("\nRunning full workflow...")
    # run_multi_agent_system("full")
