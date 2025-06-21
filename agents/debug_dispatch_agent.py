import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pandas as pd
from agents.dispatch_ops_agent import dispatch_ops_agent

def test_dispatch_agent_with_proper_data():
    """
    Test the dispatch agent with properly structured data to identify issues.
    """
    print("🔍 Debugging Dispatch Agent with Proper Data")
    print("=" * 60)
    
    # Create test state with all required fields
    test_state = {
        "messages": [],
        # Crew schedule with FAA violations - INCLUDING ROLE FIELD
        "crew_schedule": [
            {
                "crew_id": "C001",
                "assigned_flight": "UA101",
                "duty_start": datetime.now().isoformat(),
                "duty_end": (datetime.now() + timedelta(hours=12)).isoformat(),  # ❌ exceeds 10 hours
                "rest_hours_prior": 8,  # ❌ below minimum 10
                "fatigue_score": 1.1,   # ❌ exceeds 1.0
                "role": "Pilot",        # ✅ Added missing role field
                "base": "ORD",
                "name": "Capt. Smith"
            }
        ],
        # Weather data with issues
        "weather_data": {
            "DepartureWeather": ["TS"]  # ❌ Thunderstorm
        },
        # Fuel data with issues
        "fuel_data": {
            "DepartureFuel": "FUEL ORDER"  # ❌ Not fueled
        }
    }
    
    print("📋 Test State:")
    print(f"  Crew schedule: {len(test_state['crew_schedule'])} crew members")
    print(f"  Weather data: {test_state['weather_data']}")
    print(f"  Fuel data: {test_state['fuel_data']}")
    
    try:
        # Test the dispatch agent
        result = dispatch_ops_agent(test_state)
        
        print("\n✅ Dispatch Agent Results:")
        print(f"  Dispatch status: {result.get('dispatch_status')}")
        print(f"  Crew legality: {result.get('crew_legality_status')}")
        print(f"  Weather status: {result.get('weather_status')}")
        print(f"  Fuel status: {result.get('fuel_status')}")
        print(f"  Violations: {result.get('dispatch_violations')}")
        print(f"  Messages: {result.get('messages', [])}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Dispatch Agent Failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_dispatch_agent_with_legal_crew():
    """
    Test the dispatch agent with legal crew data to see if it passes.
    """
    print("\n🔍 Testing Dispatch Agent with Legal Crew Data")
    print("=" * 60)
    
    # Create test state with legal crew
    test_state = {
        "messages": [],
        # Crew schedule with NO FAA violations
        "crew_schedule": [
            {
                "crew_id": "C001",
                "assigned_flight": "UA101",
                "duty_start": datetime.now().isoformat(),
                "duty_end": (datetime.now() + timedelta(hours=8)).isoformat(),  # ✅ within 10 hours
                "rest_hours_prior": 12,  # ✅ above minimum 10
                "fatigue_score": 0.3,    # ✅ below maximum 1.0
                "role": "Pilot",         # ✅ Added missing role field
                "base": "ORD",
                "name": "Capt. Smith"
            }
        ],
        # Weather data with issues
        "weather_data": {
            "DepartureWeather": ["TS"]  # ❌ Thunderstorm
        },
        # Fuel data with issues
        "fuel_data": {
            "DepartureFuel": "FUEL ORDER"  # ❌ Not fueled
        }
    }
    
    print("📋 Legal Crew Test State:")
    print(f"  Crew schedule: {len(test_state['crew_schedule'])} crew members")
    print(f"  Weather data: {test_state['weather_data']}")
    print(f"  Fuel data: {test_state['fuel_data']}")
    
    try:
        # Test the dispatch agent
        result = dispatch_ops_agent(test_state)
        
        print("\n✅ Dispatch Agent Results (Legal Crew):")
        print(f"  Dispatch status: {result.get('dispatch_status')}")
        print(f"  Crew legality: {result.get('crew_legality_status')}")
        print(f"  Weather status: {result.get('weather_status')}")
        print(f"  Fuel status: {result.get('fuel_status')}")
        print(f"  Violations: {result.get('dispatch_violations')}")
        print(f"  Messages: {result.get('messages', [])}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Dispatch Agent Failed (Legal Crew): {e}")
        import traceback
        traceback.print_exc()
        return None

def test_dispatch_agent_with_minimal_data():
    """
    Test the dispatch agent with minimal data to see what happens.
    """
    print("\n🔍 Testing Dispatch Agent with Minimal Data")
    print("=" * 60)
    
    # Create minimal test state
    test_state = {
        "messages": [],
        "crew_schedule": [],  # Empty crew schedule
        "weather_data": {},   # Empty weather data
        "fuel_data": {}       # Empty fuel data
    }
    
    print("📋 Minimal Test State:")
    print(f"  Crew schedule: Empty")
    print(f"  Weather data: Empty")
    print(f"  Fuel data: Empty")
    
    try:
        # Test the dispatch agent
        result = dispatch_ops_agent(test_state)
        
        print("\n✅ Dispatch Agent Results (Minimal Data):")
        print(f"  Dispatch status: {result.get('dispatch_status')}")
        print(f"  Crew legality: {result.get('crew_legality_status')}")
        print(f"  Weather status: {result.get('weather_status')}")
        print(f"  Fuel status: {result.get('fuel_status')}")
        print(f"  Violations: {result.get('dispatch_violations')}")
        print(f"  Messages: {result.get('messages', [])}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Dispatch Agent Failed (Minimal Data): {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test with proper data (including violations)
    result1 = test_dispatch_agent_with_proper_data()
    
    # Test with legal crew data
    result2 = test_dispatch_agent_with_legal_crew()
    
    # Test with minimal data
    result3 = test_dispatch_agent_with_minimal_data()
    
    print("\n📊 Summary:")
    print("=" * 60)
    if result1:
        print("✅ Dispatch agent works with proper data (violations)")
    else:
        print("❌ Dispatch agent fails with proper data (violations)")
    
    if result2:
        print("✅ Dispatch agent works with legal crew data")
    else:
        print("❌ Dispatch agent fails with legal crew data")
    
    if result3:
        print("✅ Dispatch agent works with minimal data")
    else:
        print("❌ Dispatch agent fails with minimal data") 