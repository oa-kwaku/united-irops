import pandas as pd
from typing import Dict, Any, List
from services.database_mcp_client import get_database_client

# Global database client instance
_database_client = None

def get_database_client_instance():
    """Get or create the global database client instance."""
    global _database_client
    if _database_client is None:
        _database_client = get_database_client()
    return _database_client

# FAA rule thresholds
MAX_DUTY_HOURS = 10
MIN_REST_HOURS = 10
MAX_FATIGUE_SCORE = 1.0

# FAA legality checker
def check_legality_tool(crew_schedule: List[Dict[str, Any]]) -> List[str]:
    """
    Check FAA legality for crew assignments.
    """
    if all("crew" in item and "flight_id" in item for item in crew_schedule):
        flat_crew = []
        for flight in crew_schedule:
            for crew in flight["crew"]:
                crew["assigned_flight"] = flight["flight_id"]
                flat_crew.append(crew)
        crew_schedule = flat_crew

    df = pd.DataFrame(crew_schedule)
    required_cols = ["assigned_flight", "duty_start", "duty_end", "rest_hours_prior", "fatigue_score"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required fields: {missing_cols}")

    violations = []
    for flight_id, group in df.groupby("assigned_flight"):
        for _, row in group.iterrows():
            duty_hours = (pd.to_datetime(row["duty_end"]) - pd.to_datetime(row["duty_start"])) / pd.Timedelta(hours=1)
            if duty_hours > MAX_DUTY_HOURS or row["rest_hours_prior"] < MIN_REST_HOURS or row["fatigue_score"] > MAX_FATIGUE_SCORE:
                violations.append(flight_id)
                break
    return list(set(violations))

# Pull unassigned crew from the database
def get_unassigned_crew_from_db() -> List[Dict[str, Any]]:
    """
    Get unassigned crew members from the database via MCP client.
    """
    try:
        db_client = get_database_client_instance()
        
        # Try to use the MCP client first
        try:
            crew_data = db_client.query_crew(
                assigned_flight=None,  # This will now look for NULL or "UNASSIGNED"
                min_rest_hours=MIN_REST_HOURS,
                max_fatigue_score=MAX_FATIGUE_SCORE
            )
            return crew_data
        except AttributeError:
            # MCP client doesn't have query_crew method yet, fallback to direct SQLite
            import sqlite3
            print("🔄 Database MCP not avilable - Falling back to direct SQLite connection...")
            conn = sqlite3.connect("../database/united_ops.db")
            query = """
                SELECT crew_id, name, base, rest_hours_prior, fatigue_score, role
                FROM crew
                WHERE (assigned_flight IS NULL OR assigned_flight = 'UNASSIGNED')
                  AND rest_hours_prior >= ?
                  AND fatigue_score <= ?
            """
            df = pd.read_sql_query(query, conn, params=[MIN_REST_HOURS, MAX_FATIGUE_SCORE])
            conn.close()
            return df.to_dict(orient="records")
        
    except Exception as e:
        print(f"⚠️ Error getting unassigned crew: {e}")
        
        # Final fallback: try to get all crew and filter in memory
        try:
            import sqlite3
            conn = sqlite3.connect("../database/united_ops.db")
            df = pd.read_sql_query("SELECT * FROM crew", conn)
            conn.close()
            
            # Filter in memory for unassigned crew
            unassigned_crew = [
                crew for crew in df.to_dict(orient="records")
                if (crew.get('assigned_flight') is None or crew.get('assigned_flight') == 'UNASSIGNED')
                and crew.get('rest_hours_prior', 0) >= MIN_REST_HOURS
                and crew.get('fatigue_score', 1.0) <= MAX_FATIGUE_SCORE
            ]
            
            return unassigned_crew
            
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")
            return []

# Suggest substitute crew
def propose_substitutes_tool(violations: List[str], crew_schedule: List[Dict[str, Any]], unassigned_crew: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Propose substitute crew members for flights with violations.
    """
    df = pd.DataFrame(crew_schedule)
    unassigned = pd.DataFrame(unassigned_crew)
    substitutions = {}
    for flight_id in violations:
        needed_roles = df[df["assigned_flight"] == flight_id]["role"].value_counts()
        crew_ids = []
        for role, count in needed_roles.items():
            eligible = unassigned[unassigned["role"] == role]
            selected = eligible.head(count)
            crew_ids.extend(selected["crew_id"].tolist())
            unassigned = unassigned[~unassigned["crew_id"].isin(selected["crew_id"])]
        substitutions[flight_id] = crew_ids
    return substitutions

# FAA legality compliance check with auto-substitution
def check_faa_legality_compliance(state: Dict[str, Any]) -> bool:
    """
    Check FAA legality and propose substitutions if needed.
    """
    try:
        crew_schedule = state.get("crew_schedule", [])
        if not crew_schedule:
            state.setdefault("messages", []).append("No crew schedule provided.")
            return False

        # Convert DataFrame to list of dictionaries if needed
        if hasattr(crew_schedule, 'to_dict'):
            crew_schedule = crew_schedule.to_dict('records')

        violations = check_legality_tool(crew_schedule)
        state["legality_flags"] = violations

        if not violations:
            state.setdefault("messages", []).append("FAA Check: Original crew is legal.")
            return True

        unassigned_crew = get_unassigned_crew_from_db()
        substitutions = propose_substitutes_tool(
            violations=violations,
            crew_schedule=crew_schedule,
            unassigned_crew=unassigned_crew
        )

        state["crew_substitutions"] = substitutions

        for flight_id in violations:
            if substitutions.get(flight_id):
                state.setdefault("messages", []).append(f"FAA Check: Substitution successful for flight {flight_id}: {substitutions[flight_id]}")
                state.setdefault("proposals", []).append({
                    "agent": "FAAComplianceChecker",
                    "flight": flight_id,
                    "action": "Substitution",
                    "reason": "FAA violation",
                    "crew": substitutions[flight_id]
                })
            else:
                state.setdefault("messages", []).append(f"FAA Check: No substitute available for flight {flight_id}.")
                return False

        return True

    except Exception as e:
        state.setdefault("messages", []).append(f"FAA legality check failed: {e}")
        return False

# Weather risk detection with time windows
def detect_weather_risks(departure_weather: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect weather risks that could cause delays.
    Enhanced to handle time windows and return structured weather alerts.
    
    Expected input format:
    {
        "DepartureWeather": ["TS", "FG"],
        "weather_start_time": "2025-06-25 14:00:00",
        "weather_end_time": "2025-06-25 18:00:00",
        "airport": "ORD"
    }
    """
    metar = departure_weather.get("DepartureWeather", [])
    start_time = departure_weather.get("weather_start_time")
    end_time = departure_weather.get("weather_end_time")
    airport = departure_weather.get("airport", "ORD")

    delay_codes = {
        "TS": "Thunderstorm in vicinity (delay expected)",
        "FG": "Fog reported (delay expected)",
        "SN": "Snow present at departure (delay expected)",
    }
    
    weather_risks = {code: msg for code, msg in delay_codes.items() if code in metar}
    
    if weather_risks:
        return {
            "weather_codes": list(weather_risks.keys()),
            "weather_messages": weather_risks,
            "start_time": start_time,
            "end_time": end_time,
            "airport": airport,
            "has_weather_risk": True
        }
    else:
        return {
            "weather_codes": [],
            "weather_messages": {},
            "start_time": start_time,
            "end_time": end_time,
            "airport": airport,
            "has_weather_risk": False
        }

# Query database for flights affected by weather
def get_flights_affected_by_weather(weather_alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Query the database to find flights departing from or arriving at the affected airport
    during the weather alert time window.
    
    Args:
        weather_alert: Dictionary containing weather alert information with time windows
        
    Returns:
        List of flights affected by the weather conditions
    """
    try:
        db_client = get_database_client_instance()
        
        airport = weather_alert.get("airport", "ORD")
        start_time = weather_alert.get("start_time")
        end_time = weather_alert.get("end_time")
        
        if not start_time or not end_time:
            print("⚠️ Weather alert missing time windows, cannot query affected flights")
            return []
        
        print(f"🔍 Querying flights at {airport} between {start_time} and {end_time}")
        
        # Query flights departing from the affected airport
        departing_flights = db_client.query_flights(departure_location=airport)
        
        # Query flights arriving at the affected airport
        arriving_flights = db_client.query_flights(arrival_location=airport)
        
        # Combine all flights
        all_flights = departing_flights + arriving_flights
        
        # Filter flights by time window
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        affected_flights = []
        for flight in all_flights:
            # Check departure time if this is a departing flight
            if flight.get('departure_location') == airport and flight.get('departure_time'):
                try:
                    flight_departure = datetime.fromisoformat(flight['departure_time'].replace('Z', '+00:00'))
                    if start_dt <= flight_departure <= end_dt:
                        flight['weather_impact'] = 'departure_delay'
                        affected_flights.append(flight)
                except Exception as e:
                    print(f"⚠️ Could not parse departure time for flight {flight.get('flight_number')}: {e}")
            
            # Check arrival time if this is an arriving flight
            elif flight.get('arrival_location') == airport and flight.get('arrival_time'):
                try:
                    flight_arrival = datetime.fromisoformat(flight['arrival_time'].replace('Z', '+00:00'))
                    if start_dt <= flight_arrival <= end_dt:
                        flight['weather_impact'] = 'arrival_delay'
                        affected_flights.append(flight)
                except Exception as e:
                    print(f"⚠️ Could not parse arrival time for flight {flight.get('flight_number')}: {e}")
        
        # Remove duplicates based on flight_number
        seen_flights = set()
        unique_flights = []
        for flight in affected_flights:
            if flight['flight_number'] not in seen_flights:
                seen_flights.add(flight['flight_number'])
                unique_flights.append(flight)
        
        print(f"📊 Found {len(unique_flights)} flights affected by weather at {airport}")
        
        return unique_flights
        
    except Exception as e:
        print(f"❌ Error querying affected flights: {e}")
        return []

# Enhanced weather analysis with flight impact assessment
def analyze_weather_impact(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive weather analysis including affected flights.
    
    Args:
        weather_data: Weather data with time windows and airport information
        
    Returns:
        Dictionary containing weather analysis and affected flights
    """
    # Detect weather risks
    weather_alert = detect_weather_risks(weather_data)
    
    if weather_alert.get("has_weather_risk"):
        # Query affected flights
        affected_flights = get_flights_affected_by_weather(weather_alert)
        
        # Calculate impact metrics
        departure_delays = [f for f in affected_flights if f.get('weather_impact') == 'departure_delay']
        arrival_delays = [f for f in affected_flights if f.get('weather_impact') == 'arrival_delay']
        
        impact_summary = {
            "total_affected_flights": len(affected_flights),
            "departure_delays": len(departure_delays),
            "arrival_delays": len(arrival_delays),
            "affected_airport": weather_alert.get("airport"),
            "weather_duration_hours": None  # Will calculate if times are provided
        }
        
        # Calculate weather duration if times are provided
        if weather_alert.get("start_time") and weather_alert.get("end_time"):
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(weather_alert["start_time"].replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(weather_alert["end_time"].replace('Z', '+00:00'))
                duration = (end_dt - start_dt).total_seconds() / 3600
                impact_summary["weather_duration_hours"] = round(duration, 1)
            except Exception as e:
                print(f"⚠️ Could not calculate weather duration: {e}")
        
        return {
            "weather_alert": weather_alert,
            "affected_flights": affected_flights,
            "impact_summary": impact_summary,
            "has_weather_risk": True
        }
    else:
        return {
            "weather_alert": weather_alert,
            "affected_flights": [],
            "impact_summary": {
                "total_affected_flights": 0,
                "departure_delays": 0,
                "arrival_delays": 0,
                "affected_airport": weather_alert.get("airport"),
                "weather_duration_hours": 0
            },
            "has_weather_risk": False
        }

# Fuel readiness check
def detect_fuel_capacity(departure_fuel: Dict[str, Any]) -> Dict[str, str]:
    """
    Checks fuel readiness before dispatch using 'DepartureFuel' key.
    Acceptable values: 'FUEL FINAL' (ready), 'FUEL ORDER' (not yet fueled).
    """
    fuel_status = departure_fuel.get("DepartureFuel", [])

    if fuel_status == "FUEL FINAL":
        return {}  # ✅ Ready to dispatch

    if fuel_status == "FUEL ORDER":
        return {"FUEL_REQUESTED": "Airplane needs fuel prior to departure."}

    return {"FUEL_DATA_MISSING": "No fuel data provided: 'DepartureFuel' key missing or invalid."}

def dispatch_ops_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch Operations Agent that evaluates crew legality, fuel status, and weather conditions before dispatch.
    
    This agent:
    1. Checks FAA crew legality compliance
    2. Evaluates weather conditions for potential delays
    3. Verifies fuel readiness
    4. Provides overall dispatch approval status
    
    Returns:
        Updated state with dispatch status and any violations found
    """
    print("🛰️ DispatchOpsAgent activated")
    state.setdefault("messages", []).append("DispatchOpsAgent checking dispatch readiness")

    # Get run_id from state for logging
    run_id = state.get("run_id", "default")

    # Initialize
    violations = {}
    crew_legality_status = "GREEN"
    weather_status = "GREEN"
    fuel_status = "GREEN"

    # ✅ Crew legality check - use results from crew ops agent if available
    crew_substitutions = state.get("crew_substitutions", {})
    legality_flags = state.get("legality_flags", [])
    
    if legality_flags and not crew_substitutions:
        # Crew ops found violations but no substitutions available
        crew_legality_status = "EXCEPTION"
        violations["CREW_LEGALITY"] = "FAA legality failed and no substitution was possible."
        state["messages"].append("Crew legality: ❌ Violations found but no substitutions available")
    elif legality_flags and crew_substitutions:
        # Crew ops found violations and provided substitutions
        crew_legality_status = "GREEN"  # Substitutions available
        state["messages"].append("Crew legality: ✅ Substitutions available")
    else:
        # No violations found
        crew_legality_status = "GREEN"
        state["messages"].append("Crew legality: ✅ Passed")

    # 🌤️ Weather risk check - Enhanced with time windows and affected flights
    weather_analysis = analyze_weather_impact(state.get("weather_data", {}))
    
    if weather_analysis.get("has_weather_risk"):
        weather_status = "EXCEPTION"
        
        # Add weather violations to the violations dict
        weather_alert = weather_analysis["weather_alert"]
        weather_messages = weather_alert.get("weather_messages", {})
        violations.update(weather_messages)
        
        # Add affected flights to state
        state["weather_affected_flights"] = weather_analysis["affected_flights"]
        state["weather_impact_summary"] = weather_analysis["impact_summary"]
        
        # Log weather impact
        impact_summary = weather_analysis["impact_summary"]
        state["messages"].append(
            f"Weather alert: {len(weather_alert.get('weather_codes', []))} weather conditions detected "
            f"at {impact_summary['affected_airport']} affecting {impact_summary['total_affected_flights']} flights "
            f"({impact_summary['departure_delays']} departures, {impact_summary['arrival_delays']} arrivals)"
        )
        
        if impact_summary.get("weather_duration_hours"):
            state["messages"].append(f"Weather expected to last {impact_summary['weather_duration_hours']} hours")
    else:
        state["messages"].append("Weather conditions: ✅ Clear")
        state["weather_affected_flights"] = []
        state["weather_impact_summary"] = weather_analysis["impact_summary"]

    # ⛽ Fuel readiness check
    fuel_issues = detect_fuel_capacity(state.get("fuel_data", {}))
    if fuel_issues:
        fuel_status = "EXCEPTION"
        violations.update(fuel_issues)
    else:
        state["messages"].append("Fuel check: ✅ Sufficient")

    # 🟢 Overall readiness: all 3 must be GREEN
    overall_status = "GREEN" if all([
        crew_legality_status == "GREEN",
        weather_status == "GREEN",
        fuel_status == "GREEN"
    ]) else "EXCEPTION"

    state["messages"].append(
        "DispatchOpsAgent approved dispatch readiness." if overall_status == "GREEN"
        else "DispatchOpsAgent found dispatch violations."
    )

    # Log final status with run_id
    try:
        from agents.crew_ops_agent import log_message_tool
        log_message_tool.invoke({
            "agent_name": "DispatchOpsAgent", 
            "message": f"Dispatch status: {overall_status}. Violations: {list(violations.keys()) if violations else 'None'}",
            "run_id": run_id
        })
    except Exception as e:
        print(f"⚠️ Failed to log message: {e}")

    # Final result
    return {
        **state,
        "crew_legality_status": crew_legality_status,
        "weather_status": weather_status,
        "fuel_status": fuel_status,
        "dispatch_status": overall_status,
        "dispatch_violations": violations
    }

def test_dispatch_ops_agent():
    """
    Test function for the dispatch operations agent
    """
    print("Testing dispatch operations agent...")
    
    from datetime import datetime, timedelta
    
    # Sample state with various scenarios
    test_state = {
        "crew_schedule": [
            {
                "crew_id": "C001",
                "assigned_flight": "UA101",
                "duty_start": (datetime.now()).isoformat(),
                "duty_end": (datetime.now() + timedelta(hours=12)).isoformat(),  # ❌ exceeds 10 hours
                "rest_hours_prior": 8,  # ❌ below minimum 10
                "fatigue_score": 1.1,   # ❌ exceeds 1.0
                "role": "Pilot",
                "base": "ORD",
                "name": "Capt. Smith"
            }
        ],
        "weather_data": {
            "DepartureWeather": ["TS"]  # ❌ Thunderstorm
        },
        "fuel_data": {
            "DepartureFuel": "FUEL ORDER"  # ❌ Not fueled
        },
        "messages": []
    }
    
    # Test the dispatch operations agent
    result = dispatch_ops_agent(test_state)
    
    print("\nTest Results:")
    print(f"Dispatch status: {result.get('dispatch_status')}")
    print(f"Crew legality: {result.get('crew_legality_status')}")
    print(f"Weather status: {result.get('weather_status')}")
    print(f"Fuel status: {result.get('fuel_status')}")
    print(f"Violations: {result.get('dispatch_violations')}")
    print(f"Messages: {result.get('messages', [])}")
    
    return result

if __name__ == "__main__":
    test_dispatch_ops_agent() 