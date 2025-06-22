# Demo Scenario File

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import Dict, Any, TypedDict, List, NotRequired
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import LangGraph components
from langgraph.graph import StateGraph, END, START

# Import agents
from agents.planner_agent import planner_agent
from agents.crew_ops_agent import crew_ops_agent
from agents.dispatch_ops_agent import dispatch_ops_agent

# Define the state for the graph
class DemoState(TypedDict):
    run_id: str
    messages: List[str]
    # Weather data
    weather_data: NotRequired[Dict[str, Any]]
    fuel_data: NotRequired[Dict[str, Any]]
    # Crew data
    crew_schedule: NotRequired[pd.DataFrame]
    # Agent outputs
    legality_flags: NotRequired[List[str]]
    crew_substitutions: NotRequired[Dict[str, List[str]]]
    dispatch_status: NotRequired[str]
    dispatch_violations: NotRequired[Dict[str, Any]]
    weather_affected_flights: NotRequired[List[Dict[str, Any]]]
    # Planning
    plan_summary: NotRequired[str]
    # Workflow control
    workflow_sequence: NotRequired[List[str]]
    current_step: NotRequired[int]
    routing_logic: NotRequired[str]

def create_intelligent_routing_demo():
    """
    Creates a LangGraph demo that demonstrates intelligent routing:
    1. Initial router analyzes state and sets workflow sequence
    2. Weather alert detected -> Dispatch ops first, then crew ops, then dispatch again
    3. Crew issues detected -> Crew ops, then dispatch
    4. Planner generates summary
    """
    print("Creating intelligent routing demo graph...")
    
    # Create the graph
    workflow = StateGraph(DemoState)
    
    # Define the initial router node
    def initial_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes initial state and sets up the workflow sequence.
        """
        print("\n--- INITIAL ROUTER ---")
        print("Analyzing initial state and determining workflow sequence...")
        
        # Check for weather alerts and crew issues
        weather_data = state.get("weather_data", {})
        weather_codes = weather_data.get("DepartureWeather", [])
        has_weather_alert = weather_codes and any(code in ["TS", "FG", "SN"] for code in weather_codes)
        
        has_crew_schedule = "crew_schedule" in state and not state["crew_schedule"].empty
        
        # Determine workflow sequence based on conditions
        if has_weather_alert and has_crew_schedule:
            # Weather alert + crew issues: dispatch -> crew -> dispatch -> planner
            workflow_sequence = ["dispatch_ops", "crew_ops", "dispatch_ops", "planner"]
            routing_logic = "Weather alert detected, then crew issues - dispatch will re-evaluate after crew substitutions"
        elif has_weather_alert:
            # Weather alert only: dispatch -> planner
            workflow_sequence = ["dispatch_ops", "planner"]
            routing_logic = "Weather alert detected - dispatch assessment only"
        elif has_crew_schedule:
            # Crew issues only: crew -> dispatch -> planner
            workflow_sequence = ["crew_ops", "dispatch_ops", "planner"]
            routing_logic = "Crew issues detected - crew ops then dispatch assessment"
        else:
            # Default: dispatch -> planner
            workflow_sequence = ["dispatch_ops", "planner"]
            routing_logic = "Default assessment - dispatch ops only"
        
        # Set up the workflow state
        state.update({
            "workflow_sequence": workflow_sequence,
            "current_step": 0,
            "routing_logic": routing_logic
        })
        
        print(f"Workflow sequence: {' -> '.join(workflow_sequence)}")
        print(f"Routing logic: {routing_logic}")
        
        return state
    
    # Define the routing decision function
    def routing_decision(state: Dict[str, Any]) -> str:
        """
        Routes based on the workflow sequence and current step.
        """
        workflow_sequence = state.get("workflow_sequence", [])
        current_step = state.get("current_step", 0)
        
        print(f"[ROUTING DEBUG] Current step: {current_step}, Sequence: {workflow_sequence}")
        
        # Check if we've completed all steps
        if current_step >= len(workflow_sequence):
            print("  [ROUTING DEBUG] Workflow complete, ending")
            return "end"
        
        # Get the next node from the sequence
        next_node = workflow_sequence[current_step]
        print(f"  [ROUTING DEBUG] Routing to: {next_node}")
        
        return next_node
    
    # Define the agent nodes
    def dispatch_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- DISPATCH OPS AGENT ---")
        print("Analyzing weather conditions and dispatch readiness...")
        result = dispatch_ops_agent(state)
        print(f"[DEMO DEBUG] After dispatch_ops_node, delay_advisories: {result.get('delay_advisories', [])}")
        # Increment the step after completing the node
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    def crew_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- CREW OPS AGENT ---")
        print("Analyzing FAA compliance and crew substitutions...")
        result = crew_ops_agent(state)
        print(f"[DEMO DEBUG] After crew_ops_node, delay_advisories: {result.get('delay_advisories', [])}")
        # Increment the step after completing the node
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n--- PLANNER AGENT ---")
        print("Generating executive summary...")
        print(f"[DEMO DEBUG] At start of planner_node, delay_advisories: {state.get('delay_advisories', [])}")
        run_id = state.get("run_id", "demo-scenario")
        result = planner_agent(state, run_id=run_id)
        print(f"[DEMO DEBUG] After planner_node, delay_advisories: {result.get('delay_advisories', [])}")
        # Increment the step after completing the node
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    # Add nodes to the graph
    workflow.add_node("initial_router", initial_router_node)
    workflow.add_node("dispatch_ops", dispatch_ops_node)
    workflow.add_node("crew_ops", crew_ops_node)
    workflow.add_node("planner", planner_node)
    
    # Set entry point
    workflow.set_entry_point("initial_router")
    
    # Add conditional edges from initial_router
    workflow.add_conditional_edges(
        "initial_router",
        routing_decision,
        {
            "dispatch_ops": "dispatch_ops",
            "crew_ops": "crew_ops",
            "planner": "planner",
            "end": END
        }
    )
    
    # Add conditional edges from dispatch_ops
    workflow.add_conditional_edges(
        "dispatch_ops",
        routing_decision,
        {
            "crew_ops": "crew_ops",
            "dispatch_ops": "dispatch_ops",
            "planner": "planner",
            "end": END
        }
    )
    
    # Add conditional edges from crew_ops
    workflow.add_conditional_edges(
        "crew_ops",
        routing_decision,
        {
            "dispatch_ops": "dispatch_ops",
            "planner": "planner",
            "end": END
        }
    )
    
    # Add edge from planner to END
    workflow.add_edge("planner", END)
    
    # Compile the graph
    app = workflow.compile()
    
    print("Intelligent routing demo graph created successfully")
    return app

def run_demo_scenario():
    """
    Runs the intelligent routing demo with weather alert and crew issues.
    """
    print("Starting Intelligent Routing Demo Scenario")
    print("=" * 60)
    
    # Create the workflow
    app = create_intelligent_routing_demo()
    
    # Define initial state with weather alert and crew issues
    run_id = f"demo-scenario-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    initial_state = {
        "run_id": run_id,
        "messages": [],
        # Weather alert (thunderstorm)
        "weather_data": {
            "DepartureWeather": ["TS", "FG"],  # Thunderstorm and fog
            "weather_start_time": "2025-06-25 14:00:00",
            "weather_end_time": "2025-06-25 18:00:00",
            "airport": "ORD"
        },
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"  # Fueled and ready
        },
        # Crew schedule with FAA violations
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C001", "C002", "C003"],
            "assigned_flight": ["UA101", "UA101", "UA102"],
            "duty_start": [
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat()
            ],
            "duty_end": [
                (datetime.now() + timedelta(hours=12)).isoformat(),  # Exceeds 10 hours
                (datetime.now() + timedelta(hours=8)).isoformat(),
                (datetime.now() + timedelta(hours=11)).isoformat()   # Exceeds 10 hours
            ],
            "rest_hours_prior": [8, 12, 9],  # First and third below minimum 10
            "fatigue_score": [1.1, 0.3, 1.2],  # First and third above maximum 1.0
            "role": ["Pilot", "Attendant", "Pilot"],
            "base": ["ORD", "ORD", "ORD"],
            "name": ["Capt. Smith", "J. Doe", "Capt. Johnson"]
        })
    }
    
    print("Initial State:")
    print(f"  - Weather: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  - Crew members: {len(initial_state['crew_schedule'])}")
    print(f"  - Run ID: {run_id}")
    
    # Invoke the graph
    print("\nExecuting intelligent routing workflow...")
    final_state = app.invoke(initial_state)
    
    # Print results
    print("\n" + "=" * 60)
    print("DEMO SCENARIO RESULTS")
    print("=" * 60)
    
    print(f"\nDispatch Operations:")
    print(f"  Status: {final_state.get('dispatch_status', 'UNKNOWN')}")
    print(f"  Weather affected flights: {len(final_state.get('weather_affected_flights', []))}")
    if final_state.get('dispatch_violations'):
        print(f"  Violations: {list(final_state.get('dispatch_violations', {}).keys())}")
    
    print(f"\nCrew Operations:")
    print(f"  Crew substitutions: {len(final_state.get('crew_substitutions', {}))}")
    print(f"  Legality flags: {len(final_state.get('legality_flags', []))}")
    if final_state.get('legality_flags'):
        print(f"  Violating flights: {final_state.get('legality_flags')}")
    
    print(f"\nPlanning:")
    if final_state.get('plan_summary'):
        summary_preview = final_state['plan_summary'][:200] + "..." if len(final_state['plan_summary']) > 200 else final_state['plan_summary']
        print(f"  Summary: {summary_preview}")
    
    print(f"\nSystem Messages ({len(final_state.get('messages', []))}):")
    for msg in final_state.get('messages', [])[-5:]:  # Show last 5 messages
        print(f"  - {msg}")
    
    print(f"\nDemo scenario completed successfully!")
    print(f"Expected flow: Weather Alert -> Dispatch Ops -> Crew Issues -> Crew Ops -> Planner")
    
    return final_state

if __name__ == "__main__":
    # Check if API key is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not found in environment variables")
        print("Please set your API key in the .env file")
        exit(1)
    
    # Run the demo
    run_demo_scenario() 