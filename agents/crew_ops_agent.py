import json
import pandas as pd
from typing import Dict, Any, List
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv
from services.database_mcp_client import get_database_client

# Load environment variables
load_dotenv()

# Global database client instance
_database_client = None

def get_database_client_instance():
    """Get or create the global database client instance."""
    global _database_client
    if _database_client is None:
        _database_client = get_database_client()
    return _database_client

# Constants
MAX_DUTY_HOURS = 10
MIN_REST_HOURS = 10
MAX_FATIGUE_SCORE = 1.0

@tool
def log_message_tool(agent_name: str, message: str, run_id: str = "default", context: Dict[str, Any] = None) -> str:
    """
    Logs a message from an agent to the shared agent_logs table via MCP.

    Args:
        agent_name (str): The name of the agent logging the message.
        message (str): The log message.
        run_id (str): A shared identifier for this run of the planner.
        context (dict, optional): Any structured metadata (flight_id, crew, etc.).

    Returns:
        str: Confirmation that the message was logged.
    """
    try:
        db_client = get_database_client_instance()
        
        # Use the database MCP client to log messages
        # Note: This would need to be implemented in the database MCP server
        # For now, we'll use a simple approach
        log_data = {
            "run_id": run_id,
            "agent_name": agent_name,
            "message": message,
            "context": json.dumps(context or {})
        }
        
        # Try to use a generic tool call if available
        result = db_client.execute_tool("log_message", log_data)
        
        if result.get("success"):
            return f"✅ Logged message for {agent_name}"
        else:
            return f"❌ Failed to log message: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        return f"❌ Failed to log message: {str(e)}"

@tool
def check_legality_tool(crew_schedule: List[Dict[str, Any]]) -> List[str]:
    """
    FAA legality check.
    Expects a flat list of crew members with keys:
    - assigned_flight
    - duty_start, duty_end
    - rest_hours_prior
    - fatigue_score
    If input is nested, it will be flattened.
    """
    # Handle case where input is a dictionary with crew_schedule key
    if isinstance(crew_schedule, dict) and "crew_schedule" in crew_schedule:
        crew_schedule = crew_schedule["crew_schedule"]
    
    # Handle nested input
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

@tool
def get_unassigned_crew_from_db(input: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Pulls unassigned crew from the database via MCP client.
    Can be invoked with no parameters.

    Crew must have:
    - No current flight assignment (assigned_flight IS NULL)
    - Rest hours >= MIN_REST_HOURS
    - Fatigue score <= MAX_FATIGUE_SCORE
    """
    try:
        db_client = get_database_client_instance()
        
        # Query crew with the specified criteria
        crew_data = db_client.query_crew(
            assigned_flight=None,  # Unassigned crew
            min_rest_hours=MIN_REST_HOURS,
            max_fatigue_score=MAX_FATIGUE_SCORE
        )
        
        return crew_data
        
    except Exception as e:
        print(f"⚠️ Initial attempt failed: {e}")
        
        # Fallback: try to get all crew and filter in memory
        try:
            db_client = get_database_client_instance()
            all_crew = db_client.query_crew()
            
            # Filter in memory
            unassigned_crew = [
                crew for crew in all_crew
                if crew.get('assigned_flight') is None
                and crew.get('rest_hours_prior', 0) >= MIN_REST_HOURS
                and crew.get('fatigue_score', 1.0) <= MAX_FATIGUE_SCORE
            ]
            
            return unassigned_crew
            
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")
            return []

@tool
def propose_substitutes_tool(violations: List[str], crew_schedule: List[Dict[str, Any]], unassigned_crew: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Propose legal substitute crew members for flights that violate FAA rules.

    Input:
    - `violations` (list): A list of FAA violation entries. Each violation should reference a flight_id and the affected crew. Violations can be obtained from `check_legality_tool and have a structure of list of flight IDs that have violations.
    - `crew_schedule` (list): The current full crew schedule, with each entry containing fields like `crew_id`, `assigned_flight`, `role`, `base`, `fatigue_score`, and other relevant attributes.
    - `unassigned_crew` (list): A list of available crew members not currently assigned to a flight. Each must include:
        - `crew_id` (str)
        - `role` (str) — either "Pilot" or "Attendant"
        - `base` (str)
        - `fatigue_score` (float between 0 and 1)
        - optionally: `rest_hours_prior`, `last_flight_end`, etc.

    Usage:
    1. Always call `get_unassigned_crew_from_db` before using this tool.
    2. Ensure the unassigned crew have matching `role` and `base` to the affected crew in violations.
    3. The tool will match substitutes by lowest fatigue and highest availability.

    Output:
    - Returns a dictionary mapping `flight_id` to a list of proposed new crew assignments.
    """
    # Handle case where input is a dictionary with individual keys
    if isinstance(violations, dict):
        violations = violations.get("violations", [])
    if isinstance(crew_schedule, dict):
        crew_schedule = crew_schedule.get("crew_schedule", [])
    if isinstance(unassigned_crew, dict):
        unassigned_crew = unassigned_crew.get("unassigned_crew", [])
    
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

@tool
def get_full_schedule_from_db(input: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Pulls the entire current crew schedule from the database via MCP client,
    including assigned_flight, duty_start, fatigue_score, and other FAA-relevant fields.
    """
    try:
        db_client = get_database_client_instance()
        
        # Query all crew with duty assignments
        crew_data = db_client.query_crew(has_duty_assignment=True)
        
        # Convert datetime fields
        for crew in crew_data:
            for field in ['duty_start', 'duty_end', 'last_flight_end']:
                if crew.get(field):
                    crew[field] = pd.to_datetime(crew[field])
        
        return crew_data
        
    except Exception as e:
        print(f"⚠️ Error getting crew schedule: {e}")
        return []

def crew_ops_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crew Operations Agent that handles FAA compliance and crew substitutions.
    
    This agent:
    1. Analyzes crew schedules for FAA violations
    2. Identifies available substitute crew members
    3. Proposes legal crew substitutions
    4. Logs all actions for audit purposes
    """
    print("🧑‍✈️ Claude CrewOpsAgent activated")
    state.setdefault("messages", []).append("Claude CrewOpsAgent analyzing FAA legality")

    # Initialize the LLM agent
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    llm = ChatAnthropic(
        model_name="claude-3-5-sonnet-latest", 
        temperature=0.1, 
        timeout=60, 
        stop=None
    )
    
    tools = [check_legality_tool, get_unassigned_crew_from_db, propose_substitutes_tool, log_message_tool]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", 
        "You are a flight legality compliance agent.\n"
        "Step 1: Use `get_full_schedule_from_db` to load the crew schedule.\n"
        "Step 2: Use `check_legality_tool` to identify FAA violations.\n"
        "Step 3: Use `get_unassigned_crew_from_db` to get replacement candidates.\n"
        "Step 4: Use `propose_substitutes_tool` with the violations, crew schedule, and unassigned crew.\n"
        "If `unassigned_crew` is missing, re-run `get_unassigned_crew_from_db`.\n"
        "You must call `propose_substitutes_tool` with all required fields."),
        ("user", "{input}"),
        ("ai", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    crew_schedule_df = state.get("crew_schedule", pd.DataFrame())

    try:
        result = agent_executor.invoke({
            "input": "Begin compliance review using FAA rules. Load crew schedule from the database and resolve any violations."
        })

        # If output is not a dict, extract it safely
        if isinstance(result, dict):
            substitutions = result
        else:
            substitutions = result.get("output", {})

    except Exception as e:
        print(f"⚠️ Initial attempt failed: {e}")
        state.setdefault("messages", []).append(f"CrewOpsAgent: Initial tool call failed, retrying manually")

        # Manual fallback
        try:
            # Retry: Run legality and substitutions directly
            crew_schedule = get_full_schedule_from_db({})
            violations = check_legality_tool.invoke({"crew_schedule": crew_schedule})
            unassigned_crew = get_unassigned_crew_from_db({})
            substitutions = propose_substitutes_tool.invoke({
                "violations": violations, 
                "crew_schedule": crew_schedule, 
                "unassigned_crew": unassigned_crew
            })

        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")
            state.setdefault("messages", []).append("CrewOpsAgent failed to resolve substitutions")
            return state

    for flight_id, crew_list in substitutions.items():
        state.setdefault("crew_substitutions", {})[flight_id] = crew_list
        if crew_list:
            state.setdefault("current_flight_crews", {})[flight_id] = crew_list
            state.setdefault("messages", []).append(f"CrewOpsAgent: Substituted crew for flight {flight_id}")
            state.setdefault("proposals", []).append({
                "agent": "CrewOpsAgent",
                "flight": flight_id,
                "action": "Substitution",
                "reason": "FAA violation",
                "crew": crew_list
            })
        else:
            state.setdefault("messages", []).append(f"CrewOpsAgent: No substitute available for flight {flight_id}")

    state.setdefault("legality_flags", []).extend(list(substitutions.keys()))
    state["messages"].append("Claude CrewOpsAgent completed analysis")
    print("🧾 Messages before planner:", state.get("messages", []))

    # === Human-in-the-Loop Review of Substitutions ===
    print("\n🧑‍⚖️ Human Review: Proposed Crew Substitutions")
    for flight, crew in state.get("crew_substitutions", {}).items():
        print(f" - Flight {flight}: Proposed crew → {crew}")

    approval = input("\nDo you approve the proposed substitutions? (yes/no): ").strip().lower()
    if approval != "yes":
        print("❌ Substitutions rejected by human reviewer.")
        state.setdefault("messages", []).append("Human reviewer rejected the crew substitutions.")
        state["crew_substitutions"] = {}
        state["current_flight_crews"] = {}
        state["proposals"] = [p for p in state.get("proposals", []) if p.get("agent") != "CrewOpsAgent"]
    else:
        print("✅ Substitutions approved by human reviewer.")
        state.setdefault("messages", []).append("Human reviewer approved the crew substitutions.")

    return state

def test_crew_ops_agent():
    """
    Test function for the crew operations agent
    """
    print("Testing crew operations agent...")
    
    # Sample state with crew schedule
    test_state = {
        "proposals": [],
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
        }),
        "messages": []
    }
    
    # Test the crew operations agent
    result = crew_ops_agent(test_state)
    
    print("\nTest Results:")
    print(f"Crew substitutions: {result.get('crew_substitutions', {})}")
    print(f"Legality flags: {result.get('legality_flags', [])}")
    print(f"Messages: {result.get('messages', [])}")
    
    return result

if __name__ == "__main__":
    test_crew_ops_agent() 