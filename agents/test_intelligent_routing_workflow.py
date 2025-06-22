import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import agents
from agents.planner_agent import planner_agent
from agents.crew_ops_agent import crew_ops_agent
from agents.dispatch_ops_agent import dispatch_ops_agent
from agents.llm_passenger_rebooking_agent import llm_passenger_rebooking_agent
from agents.confirmation_agent import confirmation_agent

def test_weather_first_routing():
    """
    Test scenario: Weather alert detected - should route to dispatch first, then crew ops
    """
    print("🌩️ Testing Weather-First Routing Scenario")
    print("=" * 80)
    
    run_id = f"weather-first-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Initial state with weather alert
    initial_state = {
        "run_id": run_id,
        "messages": [],
        "weather_data": {
            "DepartureWeather": ["TS", "FG"],  # Thunderstorm and Fog
            "weather_start_time": "2025-06-25 14:00:00",
            "weather_end_time": "2025-06-25 18:00:00",
            "airport": "ORD"
        },
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"
        },
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C001", "C002"],
            "assigned_flight": ["UA101", "UA101"],
            "duty_start": ["2025-06-25 08:00:00", "2025-06-25 08:00:00"],
            "duty_end": ["2025-06-25 18:00:00", "2025-06-25 16:00:00"],
            "rest_hours_prior": [8, 12],
            "fatigue_score": [1.1, 0.3],
            "role": ["Pilot", "Attendant"],
            "base": ["ORD", "ORD"],
            "name": ["Capt. Smith", "J. Doe"]
        })
    }
    
    print("📋 Initial State Analysis:")
    print(f"  - Weather Alert: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  - Crew Schedule: {len(initial_state['crew_schedule'])} members")
    print(f"  - Expected Routing: dispatch_ops → crew_ops → planner")
    
    # Step 1: Planner analyzes and routes
    print("\n--- Step 1: Planner Agent (Initial Analysis) ---")
    state = planner_agent(initial_state, run_id=run_id)
    
    print(f"✅ Routing Decision: {state.get('routing_logic', 'Unknown')}")
    print(f"🎯 Next Agent: {state.get('next_agent', 'Unknown')}")
    
    # Step 2: Dispatch Ops (weather assessment)
    if state.get('next_agent') == 'dispatch_ops':
        print("\n--- Step 2: Dispatch Operations Agent ---")
        state = dispatch_ops_agent(state)
        print(f"✅ Dispatch Status: {state.get('dispatch_status', 'Unknown')}")
    
    # Step 3: Planner checks completion and routes
    print("\n--- Step 3: Planner Agent (Completion Check) ---")
    state = planner_agent(state, run_id=run_id)
    print(f"🎯 Next Agent: {state.get('next_agent', 'Unknown')}")
    
    # Step 4: Crew Ops (if needed)
    if state.get('next_agent') == 'crew_ops':
        print("\n--- Step 4: Crew Operations Agent ---")
        state = crew_ops_agent(state)
        print(f"✅ Crew Substitutions: {len(state.get('crew_substitutions', {}))}")
    
    # Step 5: Final planner summary
    print("\n--- Step 5: Planner Agent (Final Summary) ---")
    state = planner_agent(state, run_id=run_id)
    
    print(f"\n✅ Weather-First Routing Test Complete!")
    print(f"📁 Summary saved to: outputs/summary_{run_id}.md")
    
    return state

def test_crew_first_routing():
    """
    Test scenario: Crew issues detected - should route directly to crew ops
    """
    print("\n👥 Testing Crew-First Routing Scenario")
    print("=" * 80)
    
    run_id = f"crew-first-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Initial state with crew issues only
    initial_state = {
        "run_id": run_id,
        "messages": [],
        "weather_data": {
            "DepartureWeather": ["SKC"]  # Clear skies
        },
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"
        },
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C003", "C004"],
            "assigned_flight": ["UA102", "UA102"],
            "duty_start": ["2025-06-25 06:00:00", "2025-06-25 06:00:00"],
            "duty_end": ["2025-06-25 18:00:00", "2025-06-25 18:00:00"],  # 12 hours - violation
            "rest_hours_prior": [6, 8],  # Below minimum
            "fatigue_score": [1.2, 0.8],
            "role": ["Pilot", "Attendant"],
            "base": ["ORD", "ORD"],
            "name": ["Capt. Johnson", "M. Wilson"]
        })
    }
    
    print("📋 Initial State Analysis:")
    print(f"  - Weather: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  - Crew Schedule: {len(initial_state['crew_schedule'])} members with violations")
    print(f"  - Expected Routing: crew_ops → planner")
    
    # Step 1: Planner analyzes and routes
    print("\n--- Step 1: Planner Agent (Initial Analysis) ---")
    state = planner_agent(initial_state, run_id=run_id)
    
    print(f"✅ Routing Decision: {state.get('routing_logic', 'Unknown')}")
    print(f"🎯 Next Agent: {state.get('next_agent', 'Unknown')}")
    
    # Step 2: Crew Ops
    if state.get('next_agent') == 'crew_ops':
        print("\n--- Step 2: Crew Operations Agent ---")
        state = crew_ops_agent(state)
        print(f"✅ Crew Substitutions: {len(state.get('crew_substitutions', {}))}")
    
    # Step 3: Final planner summary
    print("\n--- Step 3: Planner Agent (Final Summary) ---")
    state = planner_agent(state, run_id=run_id)
    
    print(f"\n✅ Crew-First Routing Test Complete!")
    print(f"📁 Summary saved to: outputs/summary_{run_id}.md")
    
    return state

def test_cancellation_routing():
    """
    Test scenario: Flight cancellation - should route through passenger rebooking workflow
    """
    print("\n✈️ Testing Cancellation Routing Scenario")
    print("=" * 80)
    
    run_id = f"cancellation-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Initial state with flight cancellation
    initial_state = {
        "run_id": run_id,
        "messages": [],
        "weather_data": {
            "DepartureWeather": ["SKC"]  # Clear skies
        },
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"
        },
        "flight_cancellation_notification": {
            "flight_number": "UA70161",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        }
    }
    
    print("📋 Initial State Analysis:")
    print(f"  - Weather: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  - Flight Cancellation: {initial_state['flight_cancellation_notification']['flight_number']}")
    print(f"  - Expected Routing: passenger_rebooking → confirmation → database_update → planner")
    
    # Step 1: Planner analyzes and routes
    print("\n--- Step 1: Planner Agent (Initial Analysis) ---")
    state = planner_agent(initial_state, run_id=run_id)
    
    print(f"✅ Routing Decision: {state.get('routing_logic', 'Unknown')}")
    print(f"🎯 Next Agent: {state.get('next_agent', 'Unknown')}")
    
    # Step 2: Passenger Rebooking
    if state.get('next_agent') == 'passenger_rebooking':
        print("\n--- Step 2: Passenger Rebooking Agent ---")
        state = llm_passenger_rebooking_agent(state)
        print(f"✅ Rebooking Proposals: {len(state.get('rebooking_proposals', []))}")
    
    # Step 3: Planner checks completion and routes
    print("\n--- Step 3: Planner Agent (Completion Check) ---")
    state = planner_agent(state, run_id=run_id)
    print(f"🎯 Next Agent: {state.get('next_agent', 'Unknown')}")
    
    # Step 4: Confirmation (simplified for test)
    if state.get('next_agent') == 'confirmation':
        print("\n--- Step 4: Confirmation Agent (Simplified) ---")
        # For testing, we'll skip the full confirmation process
        state["confirmations"] = [
            {
                "passenger_id": "PAX001",
                "passenger_name": "Test Passenger",
                "original_flight": "UA70161",
                "rebooked_flight": "UA70162",
                "response": "accept rebooking",
                "response_time": 5.2
            }
        ]
        state["messages"].append("ConfirmationAgent: Test confirmations processed")
    
    # Step 5: Database Update
    print("\n--- Step 5: Database Update ---")
    state = llm_passenger_rebooking_agent(state)  # This handles database updates
    state["messages"].append("Database updates processed")
    
    # Step 6: Final planner summary
    print("\n--- Step 6: Planner Agent (Final Summary) ---")
    state = planner_agent(state, run_id=run_id)
    
    print(f"\n✅ Cancellation Routing Test Complete!")
    print(f"📁 Summary saved to: outputs/summary_{run_id}.md")
    
    return state

def run_all_intelligent_routing_tests():
    """
    Run all intelligent routing test scenarios
    """
    print("🚀 INTELLIGENT ROUTING WORKFLOW TESTS")
    print("=" * 80)
    
    # Test 1: Weather-first routing
    weather_result = test_weather_first_routing()
    
    # Test 2: Crew-first routing
    crew_result = test_crew_first_routing()
    
    # Test 3: Cancellation routing
    cancellation_result = test_cancellation_routing()
    
    print("\n" + "=" * 80)
    print("📊 INTELLIGENT ROUTING TEST RESULTS SUMMARY")
    print("=" * 80)
    
    print(f"\n🌩️ Weather-First Test:")
    print(f"  - Dispatch Status: {weather_result.get('dispatch_status', 'Unknown')}")
    print(f"  - Crew Substitutions: {len(weather_result.get('crew_substitutions', {}))}")
    print(f"  - Workflow Complete: {weather_result.get('workflow_complete', False)}")
    
    print(f"\n👥 Crew-First Test:")
    print(f"  - Crew Substitutions: {len(crew_result.get('crew_substitutions', {}))}")
    print(f"  - Workflow Complete: {crew_result.get('workflow_complete', False)}")
    
    print(f"\n✈️ Cancellation Test:")
    print(f"  - Rebooking Proposals: {len(cancellation_result.get('rebooking_proposals', []))}")
    print(f"  - Confirmations: {len(cancellation_result.get('confirmations', []))}")
    print(f"  - Workflow Complete: {cancellation_result.get('workflow_complete', False)}")
    
    print(f"\n✅ All intelligent routing tests completed!")
    
    return {
        "weather_test": weather_result,
        "crew_test": crew_result,
        "cancellation_test": cancellation_result
    }

if __name__ == "__main__":
    run_all_intelligent_routing_tests() 