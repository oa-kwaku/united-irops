# LLM Failure Test File
# This test simulates LLM agent failures to verify the algorithmic fallback mechanism

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
from agents.llm_passenger_rebooking_agent import llm_passenger_rebooking_agent
from agents.confirmation_agent import confirmation_agent

# Define the state for the graph
class TestState(TypedDict):
    run_id: str
    messages: List[str]
    # Weather data
    weather_data: NotRequired[Dict[str, Any]]
    fuel_data: NotRequired[Dict[str, Any]]
    # Crew data
    crew_schedule: NotRequired[List[Dict[str, Any]]]
    # Agent outputs
    legality_flags: NotRequired[List[str]]
    crew_substitutions: NotRequired[Dict[str, List[str]]]
    dispatch_status: NotRequired[str]
    dispatch_violations: NotRequired[Dict[str, Any]]
    weather_affected_flights: NotRequired[List[Dict[str, Any]]]
    delay_advisories: NotRequired[List[str]]
    # Planning
    plan_summary: NotRequired[str]
    # Workflow control
    workflow_sequence: NotRequired[List[str]]
    current_step: NotRequired[int]
    routing_logic: NotRequired[str]
    # Cancellation and rebooking
    flight_cancellation_notification: NotRequired[Dict[str, Any]]
    impacted_passengers: NotRequired[List[Dict[str, Any]]]
    alternative_flights: NotRequired[List[Dict[str, Any]]]
    rebooking_proposals: NotRequired[List[Dict[str, Any]]]
    confirmations: NotRequired[List[Dict[str, Any]]]
    # Confirmation agent state fields
    sent_messages: NotRequired[List[Dict[str, Any]]]
    current_batch: NotRequired[List[Dict[str, Any]]]
    batch_ready: NotRequired[bool]
    all_responses_processed: NotRequired[bool]

def create_llm_failure_test():
    """
    Creates a LangGraph test that simulates LLM agent failures to test fallback mechanisms.
    """
    print("🧪 Creating LLM failure test workflow...")
    
    # Create the graph
    workflow = StateGraph(TestState)
    
    # Define the initial router node
    def initial_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes initial state and sets up the workflow sequence.
        """
        print("\n🚀 INITIAL ROUTER")
        print("Setting up LLM failure test scenario...")
        
        # Check for weather alerts and crew issues
        weather_data = state.get("weather_data", {})
        weather_codes = weather_data.get("DepartureWeather", [])
        has_weather_alert = weather_codes and any(code in ["TS", "FG", "SN"] for code in weather_codes)
        
        has_crew_schedule = "crew_schedule" in state and len(state["crew_schedule"]) > 0
        
        # Check for cancellation
        has_cancellation = bool(state.get("flight_cancellation_notification"))
        
        # Determine workflow sequence based on conditions
        if has_weather_alert and has_crew_schedule:
            workflow_sequence = ["dispatch_ops", "crew_ops", "dispatch_ops"]
            routing_logic = "Weather alert detected, then crew issues - dispatch will re-evaluate after crew substitutions"
        elif has_weather_alert:
            workflow_sequence = ["dispatch_ops"]
            routing_logic = "Weather alert detected - dispatch assessment only"
        elif has_crew_schedule:
            workflow_sequence = ["crew_ops", "dispatch_ops"]
            routing_logic = "Crew issues detected - crew ops then dispatch assessment"
        else:
            workflow_sequence = ["dispatch_ops"]
            routing_logic = "Default assessment - dispatch ops only"
        
        # Always end with planner, but insert rebooking workflow before planner if cancellation present
        if has_cancellation:
            workflow_sequence.extend(["rebooking", "confirmation", "database_update"])
            routing_logic += " + Flight cancellation detected - full rebooking workflow required (LLM failure test)"
        workflow_sequence.append("planner")
        
        # Set up the workflow state
        state.update({
            "workflow_sequence": workflow_sequence,
            "current_step": 0,
            "routing_logic": routing_logic
        })
        print(f"📋 Workflow sequence: {' → '.join(workflow_sequence)}")
        print(f"🎯 Routing logic: {routing_logic}")
        print("⚠️  LLM failure test mode: Will simulate LLM agent failures to test fallback")
        
        return state
    
    # Define the routing decision function
    def routing_decision(state: Dict[str, Any]) -> str:
        """
        Routes based on the workflow sequence and current step.
        """
        workflow_sequence = state.get("workflow_sequence", [])
        current_step = state.get("current_step", 0)
        
        # Check if we've completed all steps
        if current_step >= len(workflow_sequence):
            return "end"
        
        # Get the next node from the sequence
        next_node = workflow_sequence[current_step]
        
        return next_node
    
    # Define the agent nodes
    def dispatch_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n🛰️ DISPATCH OPERATIONS")
        print("Analyzing weather conditions and dispatch readiness...")
        result = dispatch_ops_agent(state)
        # Increment the step after completing the node
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    def crew_ops_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n👨‍✈️ CREW OPERATIONS")
        print("Analyzing FAA compliance and crew substitutions...")
        result = crew_ops_agent(state)
        # Increment the step after completing the node
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n🧠 EXECUTIVE PLANNER")
        print("Generating comprehensive executive summary...")
        run_id = state.get("run_id", "llm-failure-test")
        result = planner_agent(state, run_id=run_id)
        # Increment the step after completing the node
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    def rebooking_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n🎫 PASSENGER REBOOKING (LLM FAILURE TEST)")
        print("Handling passenger rebooking with simulated LLM failure...")
        
        # Simulate LLM failure by temporarily removing API key
        original_api_key = os.getenv("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = ""  # Clear the API key to force fallback
        
        try:
            result = llm_passenger_rebooking_agent(state)
        finally:
            # Restore the API key
            if original_api_key:
                os.environ["ANTHROPIC_API_KEY"] = original_api_key
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)
        
        result["current_step"] = result.get("current_step", 0) + 1
        return result
    
    def confirmation_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n📞 PASSENGER CONFIRMATIONS")
        print("Collecting passenger confirmations...")
        
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
        state["current_step"] = state.get("current_step", 0) + 1
        return state
    
    def database_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("\n🗄️ DATABASE UPDATE")
        
        # Save confirmations for verification before they get processed
        confirmations_to_verify = state.get("confirmations", [])
        
        # Only update database if we have confirmations
        if confirmations_to_verify:
            # Import the database update tool directly
            from agents.llm_passenger_rebooking_agent import update_passenger_records
            
            # Show progress message
            print(f"🗄️ MCP Client: Updating {len(confirmations_to_verify)} passenger records in database...")
            
            # Update the database with confirmed rebookings
            updated_count = update_passenger_records.invoke({"confirmations": confirmations_to_verify})
            print(f"✅ {updated_count} passenger updates successfully completed")
            
            state["messages"] = state.get("messages", []) + [f"Database updated: {updated_count} passenger records modified"]
        else:
            print("⚠️ No confirmations to update in database")
            state["messages"] = state.get("messages", []) + ["No passenger records updated - no confirmations available"]
        
        # Store confirmations for verification
        state["confirmations_for_verification"] = confirmations_to_verify
        state["current_step"] = state.get("current_step", 0) + 1
        return state
    
    # Add nodes to the graph
    workflow.add_node("initial_router", initial_router_node)
    workflow.add_node("dispatch_ops", dispatch_ops_node)
    workflow.add_node("crew_ops", crew_ops_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("rebooking", rebooking_node)
    workflow.add_node("confirmation", confirmation_node)
    workflow.add_node("database_update", database_update_node)
    
    # Set entry point
    workflow.set_entry_point("initial_router")
    
    # Add conditional edges from initial_router
    workflow.add_conditional_edges(
        "initial_router",
        routing_decision,
        {
            "dispatch_ops": "dispatch_ops",
            "crew_ops": "crew_ops",
            "rebooking": "rebooking",
            "confirmation": "confirmation",
            "database_update": "database_update",
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
            "rebooking": "rebooking",
            "confirmation": "confirmation",
            "database_update": "database_update",
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
            "rebooking": "rebooking",
            "confirmation": "confirmation",
            "database_update": "database_update",
            "planner": "planner",
            "end": END
        }
    )
    
    # Add conditional edges from rebooking
    workflow.add_conditional_edges(
        "rebooking",
        routing_decision,
        {
            "confirmation": "confirmation",
            "database_update": "database_update",
            "planner": "planner",
            "end": END
        }
    )
    
    # Add conditional edges from confirmation
    workflow.add_conditional_edges(
        "confirmation",
        routing_decision,
        {
            "database_update": "database_update",
            "planner": "planner",
            "end": END
        }
    )
    
    # Add conditional edges from database_update
    workflow.add_conditional_edges(
        "database_update",
        routing_decision,
        {
            "planner": "planner",
            "end": END
        }
    )
    
    # Compile the graph
    app = workflow.compile()
    
    print("✅ LLM failure test workflow created successfully")
    return app

def run_llm_failure_test():
    """
    Runs the LLM failure test to verify fallback mechanisms work correctly.
    """
    print("🧪 UNITED AIRLINES LLM FAILURE TEST")
    print("=" * 60)
    print("This test simulates LLM agent failures to verify algorithmic fallback mechanisms")
    print("=" * 60)
    
    # Create the workflow
    app = create_llm_failure_test()
    
    # Define initial state with weather alert and crew issues
    run_id = f"llm-failure-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Crew schedule with FAA violations
    crew_data = {
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
    }
    
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
        "crew_schedule": [dict(zip(crew_data.keys(), values)) for values in zip(*crew_data.values())],
        # Add a sample flight cancellation notification
        "flight_cancellation_notification": {
            "flight_number": "UA70161",
            "arrival_location": "ORD",
            "reason": "Weather cancellation"
        }
    }
    
    print("📊 Test Scenario Setup:")
    print(f"  • Weather Conditions: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  • Crew Updates for Review: {len(initial_state['crew_schedule'])}")
    print(f"  • Cancelled Flight: {initial_state['flight_cancellation_notification']['flight_number']}")
    print(f"  • Run ID: {run_id}")
    print("⚠️  LLM API key will be temporarily cleared during rebooking to simulate failure")
    
    # Invoke the graph
    print("\n🔄 Executing LLM failure test workflow...")
    final_state = app.invoke(initial_state)
    
    # Print results
    print("\n" + "=" * 60)
    print("🧪 LLM FAILURE TEST RESULTS")
    print("=" * 60)
    
    print(f"\n🛰️ Dispatch Operations:")
    print(f"  • Status: {final_state.get('dispatch_status', 'UNKNOWN')}")
    print(f"  • Weather affected flights: {len(final_state.get('weather_affected_flights', []))}")
    print(f"  • Delay advisories published: {len(final_state.get('delay_advisories', []))}")
    
    print(f"\n👨‍✈️ Crew Operations:")
    print(f"  • Crew substitutions: {len(final_state.get('crew_substitutions', {}))}")
    print(f"  • FAA violations resolved: {len(final_state.get('legality_flags', []))}")
    
    print(f"\n🎫 Passenger Rebooking:")
    print(f"  • Impacted passengers: {len(final_state.get('impacted_passengers', []))}")
    print(f"  • Alternative flights found: {len(final_state.get('alternative_flights', []))}")
    print(f"  • Confirmations collected: {len(final_state.get('confirmations', []))}")
    
    # Check if fallback was used
    workflow_type = final_state.get("workflow_type", "unknown")
    llm_analysis = final_state.get("llm_analysis", "")
    
    print(f"\n🔧 Fallback Mechanism Test:")
    if workflow_type in ["algorithmic_fallback", "critical_fallback"]:
        print(f"  ✅ FALLBACK TRIGGERED: {workflow_type}")
        print(f"  • Reason: {llm_analysis}")
        print(f"  • Status: Algorithmic assignment workflow engaged successfully")
    else:
        print(f"  ❌ FALLBACK NOT TRIGGERED: {workflow_type}")
        print(f"  • Status: LLM agent completed without failure")
    
    print(f"\n🧠 Executive Summary:")
    print(f"  • Saved markdown to outputs directory")
    
    print(f"\n✅ LLM failure test completed!")
    print(f"📄 Executive summary saved to: outputs/summary_{run_id}.md")
    
    return final_state

if __name__ == "__main__":
    # Check if API key is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not found in environment variables")
        print("Please set your API key in the .env file")
        exit(1)
    
    # Run the LLM failure test
    run_llm_failure_test() 