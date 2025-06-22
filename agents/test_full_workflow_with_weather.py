import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import all agents
from agents.dispatch_ops_agent import dispatch_ops_agent
from agents.crew_ops_agent import crew_ops_agent
from agents.llm_passenger_rebooking_agent import llm_passenger_rebooking_agent
from agents.planner_agent import planner_agent

def test_full_workflow_with_weather():
    """
    Test the complete workflow with weather alerts, crew scheduling, and passenger rebooking.
    
    Workflow:
    1. Dispatch Agent - Weather alerts and affected flights
    2. Crew Ops Agent - FAA compliance and crew scheduling
    3. Passenger Rebooking Agent - Handle cancellations and rebooking
    4. Planner Agent - Executive summary of all activities
    """
    print("🚀 Testing Full Multi-Agent Workflow with Weather Alerts")
    print("=" * 80)
    
    # Create comprehensive initial state
    run_id = f"full-workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    initial_state = {
        "run_id": run_id,
        "messages": [],
        
        # Weather alert with time window
        "weather_data": {
            "DepartureWeather": ["TS", "FG"],  # Thunderstorm + Fog
            "weather_start_time": "2025-06-25 14:00:00",
            "weather_end_time": "2025-06-25 20:00:00",
            "airport": "ORD"
        },
        
        # Fuel data
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"  # Ready
        },
        
        # Crew schedule with some FAA violations
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C001", "C002", "C003", "C004"],
            "assigned_flight": ["UA101", "UA101", "UA102", "UA102"],
            "duty_start": [
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat()
            ],
            "duty_end": [
                (datetime.now() + timedelta(hours=12)).isoformat(),  # ❌ Exceeds 10 hours
                (datetime.now() + timedelta(hours=8)).isoformat(),
                (datetime.now() + timedelta(hours=11)).isoformat(),  # ❌ Exceeds 10 hours
                (datetime.now() + timedelta(hours=7)).isoformat()
            ],
            "rest_hours_prior": [8, 12, 6, 14],  # C001 and C003 below minimum
            "fatigue_score": [1.1, 0.3, 0.9, 0.2],  # C001 above maximum
            "role": ["Pilot", "Attendant", "Pilot", "Attendant"],
            "base": ["ORD", "ORD", "ORD", "ORD"],
            "name": ["Capt. Smith", "J. Doe", "Capt. Johnson", "M. Wilson"]
        }),
        
        # Flight cancellation notification
        "flight_cancellation_notification": {
            "flight_number": "UA70161",
            "arrival_location": "ORD",
            "arrival_time": "2025-06-25 07:36:00"
        },
        
        # Initialize empty collections
        "proposals": [],
        "crew_substitutions": {},
        "legality_flags": [],
        "rebooking_proposals": [],
        "impacted_passengers": [],
        "alternative_flights": []
    }
    
    print(f"📋 Initial State:")
    print(f"  - Run ID: {run_id}")
    print(f"  - Weather: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  - Weather Window: {initial_state['weather_data']['weather_start_time']} to {initial_state['weather_data']['weather_end_time']}")
    print(f"  - Affected Airport: {initial_state['weather_data']['airport']}")
    print(f"  - Cancelled Flight: {initial_state['flight_cancellation_notification']['flight_number']}")
    print(f"  - Crew Members: {len(initial_state['crew_schedule'])}")
    print(f"  - Fuel Status: {initial_state['fuel_data']['DepartureFuel']}")
    
    # Step 1: Dispatch Agent - Weather Analysis
    print(f"\n{'='*80}")
    print("STEP 1: DISPATCH AGENT - Weather Alerts and Affected Flights")
    print(f"{'='*80}")
    
    state_after_dispatch = dispatch_ops_agent(initial_state)
    
    print(f"\n✅ Dispatch Agent Results:")
    print(f"  - Dispatch Status: {state_after_dispatch.get('dispatch_status')}")
    print(f"  - Weather Status: {state_after_dispatch.get('weather_status')}")
    print(f"  - Fuel Status: {state_after_dispatch.get('fuel_status')}")
    
    weather_impact = state_after_dispatch.get('weather_impact_summary', {})
    print(f"  - Affected Flights: {weather_impact.get('total_affected_flights', 0)}")
    print(f"  - Departure Delays: {weather_impact.get('departure_delays', 0)}")
    print(f"  - Arrival Delays: {weather_impact.get('arrival_delays', 0)}")
    print(f"  - Weather Duration: {weather_impact.get('weather_duration_hours', 0)} hours")
    
    # Step 2: Crew Operations Agent - FAA Compliance
    print(f"\n{'='*80}")
    print("STEP 2: CREW OPERATIONS AGENT - FAA Compliance and Crew Scheduling")
    print(f"{'='*80}")
    
    state_after_crew = crew_ops_agent(state_after_dispatch)
    
    print(f"\n✅ Crew Operations Results:")
    print(f"  - Crew Substitutions: {len(state_after_crew.get('crew_substitutions', {}))}")
    print(f"  - Legality Flags: {len(state_after_crew.get('legality_flags', []))}")
    print(f"  - Current Flight Crews: {len(state_after_crew.get('current_flight_crews', {}))}")
    
    if state_after_crew.get('crew_substitutions'):
        for flight, crew in state_after_crew['crew_substitutions'].items():
            print(f"    - Flight {flight}: {crew}")
    
    # Step 3: Passenger Rebooking Agent - Handle Cancellations
    print(f"\n{'='*80}")
    print("STEP 3: PASSENGER REBOOKING AGENT - Cancellation Handling and Rebooking")
    print(f"{'='*80}")
    
    state_after_rebooking = llm_passenger_rebooking_agent(state_after_crew)
    
    print(f"\n✅ Passenger Rebooking Results:")
    print(f"  - Impacted Passengers: {len(state_after_rebooking.get('impacted_passengers', []))}")
    print(f"  - Alternative Flights: {len(state_after_rebooking.get('alternative_flights', []))}")
    print(f"  - Rebooking Proposals: {len(state_after_rebooking.get('rebooking_proposals', []))}")
    
    if state_after_rebooking.get('assignment_summary'):
        summary = state_after_rebooking['assignment_summary']
        print(f"  - Assignment Rate: {summary.get('assignment_rate', 0):.1f}%")
        print(f"  - Flights Used: {summary.get('flights_used', 0)}")
        print(f"  - Total Seats Used: {summary.get('total_seats_used', 0)}")
    
    # Step 4: Planner Agent - Executive Summary
    print(f"\n{'='*80}")
    print("STEP 4: PLANNER AGENT - Executive Summary")
    print(f"{'='*80}")
    
    final_state = planner_agent(state_after_rebooking, run_id=run_id)
    
    print(f"\n✅ Planner Agent Results:")
    print(f"  - Plan Summary Generated: {bool(final_state.get('plan_summary'))}")
    print(f"  - Summary Length: {len(final_state.get('plan_summary', ''))} characters")
    
    # Final Summary
    print(f"\n{'='*80}")
    print("📊 FINAL WORKFLOW SUMMARY")
    print(f"{'='*80}")
    
    print(f"\n🌤️ Weather Impact:")
    final_weather = final_state.get('weather_impact_summary', {})
    print(f"  - Weather Conditions: {final_state.get('weather_data', {}).get('DepartureWeather', [])}")
    print(f"  - Affected Airport: {final_weather.get('affected_airport')}")
    print(f"  - Total Affected Flights: {final_weather.get('total_affected_flights', 0)}")
    print(f"  - Weather Duration: {final_weather.get('weather_duration_hours', 0)} hours")
    
    print(f"\n🧑‍✈️ Crew Operations:")
    print(f"  - Crew Substitutions: {len(final_state.get('crew_substitutions', {}))}")
    print(f"  - Legality Violations: {len(final_state.get('legality_flags', []))}")
    print(f"  - Dispatch Status: {final_state.get('dispatch_status')}")
    
    print(f"\n👥 Passenger Operations:")
    print(f"  - Cancelled Flight: {final_state.get('flight_cancellation_notification', {}).get('flight_number')}")
    print(f"  - Impacted Passengers: {len(final_state.get('impacted_passengers', []))}")
    print(f"  - Rebooking Proposals: {len(final_state.get('rebooking_proposals', []))}")
    
    if final_state.get('assignment_summary'):
        summary = final_state['assignment_summary']
        print(f"  - Success Rate: {summary.get('assignment_rate', 0):.1f}%")
        print(f"  - Alternative Flights Used: {summary.get('flights_used', 0)}")
    
    print(f"\n📝 System Messages: {len(final_state.get('messages', []))}")
    print(f"  - Last 5 messages:")
    for msg in final_state.get('messages', [])[-5:]:
        print(f"    • {msg}")
    
    print(f"\n✅ Full workflow test completed successfully!")
    print(f"📁 Executive summary saved to: outputs/summary_{run_id}.md")
    
    return final_state

if __name__ == "__main__":
    # Debug: Check if API key is loaded
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    else:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
    
    test_full_workflow_with_weather() 