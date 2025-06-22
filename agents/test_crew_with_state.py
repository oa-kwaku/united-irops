import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the crew ops agent
from agents.crew_ops_agent import crew_ops_agent

def test_crew_ops_with_state():
    """
    Test the crew ops agent with a preloaded crew schedule in state.
    """
    print("🧪 Testing Crew Ops Agent with Preloaded State Schedule")
    print("=" * 60)
    
    # Create a test state with crew schedule that has FAA violations
    test_state = {
        "run_id": f"test-state-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "messages": [],
        "crew_schedule": pd.DataFrame({
            "crew_id": ["C001", "C002", "C003"],
            "assigned_flight": ["UA101", "UA101", "UA102"],
            "duty_start": [
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat(),
                (datetime.now()).isoformat()
            ],
            "duty_end": [
                (datetime.now() + timedelta(hours=12)).isoformat(),  # ❌ 12 hours > 10 max
                (datetime.now() + timedelta(hours=8)).isoformat(),   # ✅ 8 hours OK
                (datetime.now() + timedelta(hours=11)).isoformat()   # ❌ 11 hours > 10 max
            ],
            "rest_hours_prior": [8, 12, 6],  # First and third below minimum (10 hours)
            "fatigue_score": [1.1, 0.3, 1.2],  # First and third above maximum (1.0)
            "role": ["Pilot", "Attendant", "Pilot"],
            "base": ["ORD", "ORD", "ORD"],
            "name": ["Capt. Smith", "J. Doe", "Capt. Johnson"]
        })
    }
    
    print(f"📋 Test State:")
    print(f"  - Run ID: {test_state['run_id']}")
    print(f"  - Crew Schedule: {len(test_state['crew_schedule'])} crew members")
    print(f"  - Crew 1: {test_state['crew_schedule'].iloc[0]['name']} - Rest: {test_state['crew_schedule'].iloc[0]['rest_hours_prior']}h, Fatigue: {test_state['crew_schedule'].iloc[0]['fatigue_score']}")
    print(f"  - Crew 2: {test_state['crew_schedule'].iloc[1]['name']} - Rest: {test_state['crew_schedule'].iloc[1]['rest_hours_prior']}h, Fatigue: {test_state['crew_schedule'].iloc[1]['fatigue_score']}")
    print(f"  - Crew 3: {test_state['crew_schedule'].iloc[2]['name']} - Rest: {test_state['crew_schedule'].iloc[2]['rest_hours_prior']}h, Fatigue: {test_state['crew_schedule'].iloc[2]['fatigue_score']}")
    
    print("\n" + "=" * 60)
    print("STEP 1: Testing Crew Operations Agent with State Schedule")
    print("=" * 60)
    
    # Test the crew operations agent
    result = crew_ops_agent(test_state)
    
    print("\n✅ Crew Ops Agent Results:")
    print(f"  - Crew substitutions: {len(result.get('crew_substitutions', {}))}")
    print(f"  - Legality flags: {len(result.get('legality_flags', []))}")
    print(f"  - Messages: {len(result.get('messages', []))}")
    print(f"  - Final messages:")
    for msg in result.get('messages', []):
        print(f"    - {msg}")
    
    # Check if violations were detected
    if result.get('legality_flags'):
        print(f"\n🎯 FAA Violations Detected:")
        for flight in result.get('legality_flags', []):
            print(f"  - Flight {flight} has FAA violations")
    else:
        print(f"\n✅ No FAA violations detected")
    
    # Check if substitutions were proposed
    if result.get('crew_substitutions'):
        print(f"\n🔄 Crew Substitutions Proposed:")
        for flight, crew in result.get('crew_substitutions', {}).items():
            print(f"  - Flight {flight}: {crew}")
    else:
        print(f"\n📋 No crew substitutions proposed")
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)
    
    return result

if __name__ == "__main__":
    # Debug: Check if API key is loaded
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    else:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
    
    test_crew_ops_with_state() 