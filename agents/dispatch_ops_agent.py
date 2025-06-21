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
                assigned_flight=None,  # Unassigned crew
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
                WHERE assigned_flight IS NULL
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
            
            # Filter in memory
            unassigned_crew = [
                crew for crew in df.to_dict(orient="records")
                if crew.get('assigned_flight') is None
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

# Weather risk detection
def detect_weather_risks(departure_weather: Dict[str, str]) -> Dict[str, str]:
    """
    Detect weather risks that could cause delays.
    """
    metar = departure_weather.get("DepartureWeather", [])

    delay_codes = {
        "TS": "Thunderstorm in vicinity (delay expected)",
        "FG": "Fog reported (delay expected)",
        "SN": "Snow present at departure (delay expected)",
    }
    return {code: msg for code, msg in delay_codes.items() if code in metar}

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

    # Initialize
    violations = {}
    crew_legality_status = "GREEN"
    weather_status = "GREEN"
    fuel_status = "GREEN"

    # ✅ Crew legality check (with substitution fallback)
    if not check_faa_legality_compliance(state):
        crew_legality_status = "EXCEPTION"
        violations["CREW_LEGALITY"] = "FAA legality failed and no substitution was possible."
    else:
        state["messages"].append("Crew legality: ✅ Passed")

    # 🌤️ Weather risk check
    weather_risks = detect_weather_risks(state.get("weather_data", {}))
    if weather_risks:
        weather_status = "EXCEPTION"
        violations.update(weather_risks)
    else:
        state["messages"].append("Weather conditions: ✅ Clear")

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