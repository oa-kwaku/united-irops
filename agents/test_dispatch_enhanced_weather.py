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

def test_dispatch_enhanced_weather():
    """
    Test the dispatch agent with enhanced weather functionality including time windows and affected flights.
    """
    print("🌤️ Testing Enhanced Dispatch Agent Weather Detection")
    print("=" * 70)
    
    # Test different weather scenarios with time windows
    weather_scenarios = [
        {
            "name": "Thunderstorm Alert - Afternoon",
            "weather_data": {
                "DepartureWeather": ["TS"],
                "weather_start_time": "2025-06-25 14:00:00",
                "weather_end_time": "2025-06-25 18:00:00",
                "airport": "ORD"
            },
            "expected_delay": True,
            "expected_duration": 4.0
        },
        {
            "name": "Fog Alert - Morning",
            "weather_data": {
                "DepartureWeather": ["FG"],
                "weather_start_time": "2025-06-25 06:00:00",
                "weather_end_time": "2025-06-25 10:00:00",
                "airport": "ORD"
            },
            "expected_delay": True,
            "expected_duration": 4.0
        },
        {
            "name": "Clear Skies",
            "weather_data": {
                "DepartureWeather": ["SKC"],
                "weather_start_time": "2025-06-25 12:00:00",
                "weather_end_time": "2025-06-25 16:00:00",
                "airport": "ORD"
            },
            "expected_delay": False,
            "expected_duration": 4.0
        }
    ]
    
    for scenario in weather_scenarios:
        print(f"\n{'='*70}")
        print(f"TESTING: {scenario['name']}")
        print(f"{'='*70}")
        
        # Create test state with legal crew and enhanced weather data
        test_state = {
            "run_id": f"test-enhanced-weather-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "messages": [],
            # Legal crew schedule (no violations)
            "crew_schedule": pd.DataFrame({
                "crew_id": ["C001", "C002"],
                "assigned_flight": ["UA101", "UA101"],
                "duty_start": [(datetime.now()).isoformat(), (datetime.now()).isoformat()],
                "duty_end": [(datetime.now() + timedelta(hours=8)).isoformat(), (datetime.now() + timedelta(hours=8)).isoformat()],
                "rest_hours_prior": [12, 12],  # Both above minimum
                "fatigue_score": [0.3, 0.3],   # Both below maximum
                "role": ["Pilot", "Attendant"],
                "base": ["ORD", "ORD"],
                "name": ["Capt. Smith", "J. Doe"]
            }),
            # Enhanced weather data for this scenario
            "weather_data": scenario["weather_data"],
            # Fuel data (ready)
            "fuel_data": {"DepartureFuel": "FUEL FINAL"},
            # No crew substitutions needed (legal crew)
            "crew_substitutions": {},
            "legality_flags": []  # No violations
        }
        
        print(f"📋 Test State:")
        print(f"  - Run ID: {test_state['run_id']}")
        print(f"  - Weather: {scenario['weather_data']['DepartureWeather']}")
        print(f"  - Airport: {scenario['weather_data']['airport']}")
        print(f"  - Time Window: {scenario['weather_data']['weather_start_time']} to {scenario['weather_data']['weather_end_time']}")
        print(f"  - Expected Delay: {scenario['expected_delay']}")
        print(f"  - Expected Duration: {scenario['expected_duration']} hours")
        print(f"  - Crew Legality: Legal (no violations)")
        
        # Test the dispatch agent
        result = dispatch_ops_agent(test_state)
        
        print(f"\n✅ Dispatch Agent Results:")
        print(f"  - Dispatch Status: {result.get('dispatch_status')}")
        print(f"  - Crew Legality: {result.get('crew_legality_status')}")
        print(f"  - Weather Status: {result.get('weather_status')}")
        print(f"  - Fuel Status: {result.get('fuel_status')}")
        
        # Check weather analysis results
        weather_impact_summary = result.get('weather_impact_summary', {})
        weather_affected_flights = result.get('weather_affected_flights', [])
        
        print(f"\n🌤️ Enhanced Weather Analysis:")
        print(f"  - Weather Alert: {result.get('dispatch_violations', {})}")
        print(f"  - Affected Airport: {weather_impact_summary.get('affected_airport')}")
        print(f"  - Total Affected Flights: {weather_impact_summary.get('total_affected_flights', 0)}")
        print(f"  - Departure Delays: {weather_impact_summary.get('departure_delays', 0)}")
        print(f"  - Arrival Delays: {weather_impact_summary.get('arrival_delays', 0)}")
        print(f"  - Weather Duration: {weather_impact_summary.get('weather_duration_hours', 0)} hours")
        
        # Show sample affected flights
        if weather_affected_flights:
            print(f"\n📊 Sample Affected Flights:")
            for i, flight in enumerate(weather_affected_flights[:3]):  # Show first 3
                print(f"  {i+1}. Flight {flight.get('flight_number')} - {flight.get('weather_impact')}")
                print(f"     From: {flight.get('departure_location')} To: {flight.get('arrival_location')}")
                print(f"     Departure: {flight.get('departure_time')}")
                print(f"     Arrival: {flight.get('arrival_time')}")
        
        # Verify expected vs actual
        weather_delay_detected = weather_impact_summary.get('total_affected_flights', 0) > 0 or len(result.get('dispatch_violations', {})) > 0
        
        if weather_delay_detected == scenario['expected_delay']:
            print(f"  ✅ EXPECTATION MET: Weather delay detection matches expectation")
        else:
            print(f"  ❌ EXPECTATION FAILED: Expected {scenario['expected_delay']}, got {weather_delay_detected}")
        
        # Check if dispatch status is correct
        if scenario['expected_delay']:
            expected_dispatch_status = "EXCEPTION"
        else:
            expected_dispatch_status = "GREEN"
        
        if result.get('dispatch_status') == expected_dispatch_status:
            print(f"  ✅ DISPATCH STATUS CORRECT: {expected_dispatch_status}")
        else:
            print(f"  ❌ DISPATCH STATUS WRONG: Expected {expected_dispatch_status}, got {result.get('dispatch_status')}")
        
        # Check duration calculation
        actual_duration = weather_impact_summary.get('weather_duration_hours', 0)
        if abs(actual_duration - scenario['expected_duration']) < 0.1:
            print(f"  ✅ DURATION CALCULATION CORRECT: {actual_duration} hours")
        else:
            print(f"  ❌ DURATION CALCULATION WRONG: Expected {scenario['expected_duration']}, got {actual_duration}")
        
        print(f"\n📝 Final Messages:")
        for msg in result.get('messages', []):
            print(f"  - {msg}")
    
    print(f"\n{'='*70}")
    print("✅ ALL ENHANCED WEATHER TESTS COMPLETED")
    print(f"{'='*70}")
    
    # Summary
    print(f"\n📊 ENHANCED WEATHER DETECTION SUMMARY:")
    print(f"  - The dispatch agent now supports time-based weather alerts")
    print(f"  - Weather alerts include start/end times and affected airport")
    print(f"  - Database queries find flights affected during weather windows")
    print(f"  - Impact analysis includes departure vs arrival delays")
    print(f"  - Weather duration is automatically calculated")
    print(f"  - Affected flights are classified by impact type")

if __name__ == "__main__":
    # Debug: Check if API key is loaded
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    else:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
    
    test_dispatch_enhanced_weather() 