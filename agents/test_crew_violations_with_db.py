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
from agents.crew_ops_agent import crew_ops_agent
from agents.dispatch_ops_agent import dispatch_ops_agent
from agents.planner_agent import planner_agent

def test_crew_violations_with_database_substitutions():
    """
    Test crew violations detection and database queries for potential substitutions.
    
    This test focuses on:
    1. Creating crew schedules with FAA violations
    2. Querying the database for available substitute crew
    3. Proposing legal substitutions
    4. Verifying the substitution process works correctly
    """
    print("🚀 Testing Crew Violations with Database Substitutions")
    print("=" * 80)
    
    # Create run ID for this test
    run_id = f"crew-violations-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Create initial state with crew violations
    initial_state = {
        "run_id": run_id,
        "messages": [],
        
        # Crew schedule with multiple FAA violations
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C001", "C002", "C003", "C004", "C005", "C006"],
            "assigned_flight": ["UA101", "UA101", "UA102", "UA102", "UA103", "UA103"],
            "duty_start": [
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat()
            ],
            "duty_end": [
                (datetime.now() + timedelta(hours=12)).isoformat(),  # ❌ Exceeds 10 hours
                (datetime.now() + timedelta(hours=8)).isoformat(),
                (datetime.now() + timedelta(hours=11)).isoformat(),  # ❌ Exceeds 10 hours
                (datetime.now() + timedelta(hours=7)).isoformat(),
                (datetime.now() + timedelta(hours=9)).isoformat(),
                (datetime.now() + timedelta(hours=6)).isoformat()
            ],
            "rest_hours_prior": [8, 12, 6, 14, 9, 16],  # C001 and C003 below minimum
            "fatigue_score": [1.1, 0.3, 0.9, 0.2, 1.2, 0.4],  # C001 and C005 above maximum
            "role": ["Pilot", "Attendant", "Pilot", "Attendant", "Pilot", "Attendant"],
            "base": ["ORD", "ORD", "ORD", "ORD", "ORD", "ORD"],
            "name": ["Capt. Smith", "J. Doe", "Capt. Johnson", "M. Wilson", "Capt. Brown", "A. Davis"]
        }),
        
        # Weather data (clear skies for this test)
        "weather_data": {
            "DepartureWeather": ["SKC"]  # Clear skies
        },
        
        # Fuel data (ready)
        "fuel_data": {
            "DepartureFuel": "FUEL FINAL"
        },
        
        # Initialize empty collections
        "proposals": [],
        "crew_substitutions": {},
        "legality_flags": [],
        "current_flight_crews": {}
    }
    
    print(f"📋 Test Setup:")
    print(f"  - Run ID: {run_id}")
    print(f"  - Crew Members: {len(initial_state['crew_schedule'])}")
    print(f"  - Flights: {initial_state['crew_schedule']['assigned_flight'].unique()}")
    print(f"  - Expected Violations: 3 flights (UA101, UA102, UA103)")
    print(f"  - Weather: {initial_state['weather_data']['DepartureWeather']}")
    print(f"  - Fuel: {initial_state['fuel_data']['DepartureFuel']}")
    
    # Step 1: Crew Operations Agent - Detect Violations and Query Database
    print(f"\n{'='*80}")
    print("STEP 1: CREW OPERATIONS AGENT - Violation Detection and Database Queries")
    print(f"{'='*80}")
    
    state_after_crew = crew_ops_agent(initial_state)
    
    print(f"\n✅ Crew Operations Results:")
    print(f"  - Legality Flags: {state_after_crew.get('legality_flags', [])}")
    print(f"  - Crew Substitutions: {len(state_after_crew.get('crew_substitutions', {}))}")
    print(f"  - Current Flight Crews: {len(state_after_crew.get('current_flight_crews', {}))}")
    
    # Detailed analysis of violations and substitutions
    if state_after_crew.get('legality_flags'):
        print(f"\n🔍 Violation Analysis:")
        for flight in state_after_crew['legality_flags']:
            print(f"  - Flight {flight}: FAA violation detected")
            
            # Check if substitution was found
            if flight in state_after_crew.get('crew_substitutions', {}):
                substitutes = state_after_crew['crew_substitutions'][flight]
                print(f"    ✅ Substitution available: {substitutes}")
            else:
                print(f"    ❌ No substitution available")
    
    # Step 2: Dispatch Operations Agent - Verify Crew Legality
    print(f"\n{'='*80}")
    print("STEP 2: DISPATCH OPERATIONS AGENT - Crew Legality Verification")
    print(f"{'='*80}")
    
    state_after_dispatch = dispatch_ops_agent(state_after_crew)
    
    print(f"\n✅ Dispatch Operations Results:")
    print(f"  - Dispatch Status: {state_after_dispatch.get('dispatch_status')}")
    print(f"  - Crew Legality Status: {state_after_dispatch.get('crew_legality_status')}")
    print(f"  - Weather Status: {state_after_dispatch.get('weather_status')}")
    print(f"  - Fuel Status: {state_after_dispatch.get('fuel_status')}")
    
    if state_after_dispatch.get('dispatch_violations'):
        print(f"  - Dispatch Violations: {list(state_after_dispatch['dispatch_violations'].keys())}")
    
    # Step 3: Planner Agent - Executive Summary
    print(f"\n{'='*80}")
    print("STEP 3: PLANNER AGENT - Executive Summary")
    print(f"{'='*80}")
    
    final_state = planner_agent(state_after_dispatch, run_id=run_id)
    
    print(f"\n✅ Planner Agent Results:")
    print(f"  - Plan Summary Generated: {bool(final_state.get('plan_summary'))}")
    print(f"  - Summary Length: {len(final_state.get('plan_summary', ''))} characters")
    
    # Final Analysis
    print(f"\n{'='*80}")
    print("📊 FINAL CREW VIOLATIONS ANALYSIS")
    print(f"{'='*80}")
    
    print(f"\n🧑‍✈️ Crew Operations Summary:")
    print(f"  - Total Crew Members: {len(initial_state['crew_schedule'])}")
    print(f"  - Flights with Violations: {len(final_state.get('legality_flags', []))}")
    print(f"  - Successful Substitutions: {len(final_state.get('crew_substitutions', {}))}")
    
    # Analyze each flight
    original_flights = initial_state['crew_schedule']['assigned_flight'].unique()
    for flight in original_flights:
        flight_crew = initial_state['crew_schedule'][initial_state['crew_schedule']['assigned_flight'] == flight]
        print(f"\n  Flight {flight}:")
        print(f"    - Original Crew: {len(flight_crew)} members")
        
        # Check for violations
        if flight in final_state.get('legality_flags', []):
            print(f"    - Status: ❌ FAA Violation Detected")
            
            # Check for substitutions
            if flight in final_state.get('crew_substitutions', {}):
                substitutes = final_state['crew_substitutions'][flight]
                print(f"    - Substitution: ✅ {len(substitutes)} substitutes found")
                print(f"      Substitutes: {substitutes}")
            else:
                print(f"    - Substitution: ❌ No substitutes available")
        else:
            print(f"    - Status: ✅ No violations")
    
    print(f"\n📝 System Messages ({len(final_state.get('messages', []))}):")
    for msg in final_state.get('messages', [])[-10:]:  # Show last 10 messages
        print(f"  - {msg}")
    
    print(f"\n✅ Crew violations test completed!")
    print(f"📁 Executive summary saved to: outputs/summary_{run_id}.md")
    
    return final_state

def test_database_crew_queries():
    """
    Test the database crew query functionality directly.
    """
    print("\n🔍 Testing Database Crew Queries Directly")
    print("=" * 60)
    
    try:
        from services.database_mcp_client import get_database_client
        
        db_client = get_database_client()
        
        # Test 1: Query all crew
        print("\n1. Querying all crew...")
        all_crew = db_client.query_crew()
        print(f"   Total crew in database: {len(all_crew)}")
        
        if all_crew:
            print(f"   Sample crew member: {all_crew[0]}")
        
        # Test 2: Query unassigned crew
        print("\n2. Querying unassigned crew...")
        unassigned_crew = db_client.query_crew(assigned_flight=None)
        print(f"   Unassigned crew: {len(unassigned_crew)}")
        
        if unassigned_crew:
            print(f"   Sample unassigned crew: {unassigned_crew[0]}")
        
        # Test 3: Query crew with rest hours filter
        print("\n3. Querying crew with rest hours >= 10...")
        rested_crew = db_client.query_crew(min_rest_hours=10)
        print(f"   Crew with sufficient rest: {len(rested_crew)}")
        
        # Test 4: Query crew with fatigue filter
        print("\n4. Querying crew with fatigue score <= 1.0...")
        low_fatigue_crew = db_client.query_crew(max_fatigue_score=1.0)
        print(f"   Crew with acceptable fatigue: {len(low_fatigue_crew)}")
        
        # Test 5: Query by role
        print("\n5. Querying pilots...")
        pilots = db_client.query_crew(role="Pilot")
        print(f"   Pilots: {len(pilots)}")
        
        print("\n6. Querying attendants...")
        attendants = db_client.query_crew(role="Attendant")
        print(f"   Attendants: {len(attendants)}")
        
        # Test 6: Query by base
        print("\n7. Querying ORD base crew...")
        ord_crew = db_client.query_crew(base="ORD")
        print(f"   ORD base crew: {len(ord_crew)}")
        
        # Test 7: Combined query for potential substitutes
        print("\n8. Querying potential substitutes (unassigned + rested + low fatigue)...")
        potential_substitutes = db_client.query_crew(
            assigned_flight=None,
            min_rest_hours=10,
            max_fatigue_score=1.0
        )
        print(f"   Potential substitutes: {len(potential_substitutes)}")
        
        if potential_substitutes:
            print("   Sample substitutes:")
            for i, crew in enumerate(potential_substitutes[:3]):
                print(f"     {i+1}. {crew.get('name', 'Unknown')} - {crew.get('role', 'Unknown')} - Rest: {crew.get('rest_hours_prior', 'Unknown')}h - Fatigue: {crew.get('fatigue_score', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Debug: Check if API key is loaded
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    else:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
    
    # First test database queries
    print("\n" + "="*60)
    print("DATABASE CREW QUERY TESTS")
    print("="*60)
    db_test_success = test_database_crew_queries()
    
    if db_test_success:
        # Then test the full workflow
        print("\n" + "="*60)
        print("FULL CREW VIOLATIONS WORKFLOW TEST")
        print("="*60)
        test_crew_violations_with_database_substitutions()
    else:
        print("\n❌ Skipping workflow test due to database issues") 