import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the dispatch agent
from agents.dispatch_ops_agent import dispatch_ops_agent

def test_dispatch_with_weather():
    """
    Test the dispatch agent with preloaded weather codes to generate delay alerts.
    """
    print("🧪 Testing Dispatch Agent with Weather Codes")
    print("=" * 60)
    
    # Test different weather scenarios
    weather_scenarios = [
        {
            "name": "Thunderstorm Alert",
            "weather_data": {"DepartureWeather": ["TS"]},
            "expected_delay": True
        },
        {
            "name": "Fog Alert", 
            "weather_data": {"DepartureWeather": ["FG"]},
            "expected_delay": True
        },
        {
            "name": "Snow Alert",
            "weather_data": {"DepartureWeather": ["SN"]},
            "expected_delay": True
        },
        {
            "name": "Clear Skies",
            "weather_data": {"DepartureWeather": ["SKC"]},
            "expected_delay": False
        },
        {
            "name": "Multiple Weather Issues",
            "weather_data": {"DepartureWeather": ["TS", "FG"]},
            "expected_delay": True
        }
    ]
    
    for scenario in weather_scenarios:
        print(f"\n{'='*60}")
        print(f"TESTING: {scenario['name']}")
        print(f"{'='*60}")
        
        # Create test state with crew schedule (from previous test) and weather data
        test_state = {
            "run_id": f"test-dispatch-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "messages": [],
            # Crew schedule with FAA violations (from previous test)
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
            # Weather data for this scenario
            "weather_data": scenario["weather_data"],
            # Fuel data (ready)
            "fuel_data": {"DepartureFuel": "FUEL FINAL"},
            # Crew substitutions from crew ops (empty for this test)
            "crew_substitutions": {},
            "legality_flags": ["UA101"]  # From crew ops analysis
        }
        
        print(f"📋 Test State:")
        print(f"  - Run ID: {test_state['run_id']}")
        print(f"  - Weather: {scenario['weather_data']}")
        print(f"  - Expected Delay: {scenario['expected_delay']}")
        print(f"  - Crew Legality Flags: {test_state['legality_flags']}")
        
        # Test the dispatch agent
        result = dispatch_ops_agent(test_state)
        
        print(f"\n✅ Dispatch Agent Results:")
        print(f"  - Dispatch Status: {result.get('dispatch_status')}")
        print(f"  - Crew Legality: {result.get('crew_legality_status')}")
        print(f"  - Weather Status: {result.get('weather_status')}")
        print(f"  - Fuel Status: {result.get('fuel_status')}")
        print(f"  - Violations: {result.get('dispatch_violations', {})}")
        print(f"  - Messages: {len(result.get('messages', []))}")
        
        # Check if weather delay was detected
        weather_violations = result.get('dispatch_violations', {})
        weather_delay_detected = any(key in weather_violations for key in ['TS', 'FG', 'SN'])
        
        print(f"\n🎯 Weather Analysis:")
        if weather_delay_detected:
            print(f"  ✅ Weather delay detected: {[k for k in weather_violations.keys() if k in ['TS', 'FG', 'SN']]}")
        else:
            print(f"  ✅ No weather delays detected")
        
        # Verify expected vs actual
        if weather_delay_detected == scenario['expected_delay']:
            print(f"  ✅ EXPECTATION MET: Weather delay detection matches expectation")
        else:
            print(f"  ❌ EXPECTATION FAILED: Expected {scenario['expected_delay']}, got {weather_delay_detected}")
        
        print(f"\n📝 Final Messages:")
        for msg in result.get('messages', []):
            print(f"  - {msg}")
    
    print(f"\n{'='*60}")
    print("✅ ALL WEATHER TESTS COMPLETED")
    print(f"{'='*60}")

if __name__ == "__main__":
    # Debug: Check if API key is loaded
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    else:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
    
    test_dispatch_with_weather() 