import os
import re
from typing import Dict, Any, Union, List
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_tool_calling_agent, AgentExecutor
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

@tool
def analyze_initial_state_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes the initial state to determine what issues need to be addressed.
    
    Args:
        state: The current system state
        
    Returns:
        Dictionary with analysis results including:
        - has_weather_alert: boolean
        - has_crew_issues: boolean
        - has_flight_cancellation: boolean
        - recommended_next_agent: string
        - priority_issues: list of strings
    """
    analysis = {
        "has_weather_alert": False,
        "has_crew_issues": False,
        "has_flight_cancellation": False,
        "recommended_next_agent": "crew_ops",
        "priority_issues": [],
        "analysis_summary": ""
    }
    
    # Check for weather alerts
    weather_data = state.get("weather_data", {})
    if weather_data:
        weather_codes = weather_data.get("DepartureWeather", [])
        if weather_codes and any(code in ["TS", "FG", "SN"] for code in weather_codes):
            analysis["has_weather_alert"] = True
            analysis["priority_issues"].append("Weather alert detected")
            analysis["recommended_next_agent"] = "dispatch_ops"
    
    # Check for crew issues
    crew_schedule = state.get("crew_schedule")
    if crew_schedule is not None:
        analysis["has_crew_issues"] = True
        analysis["priority_issues"].append("Crew schedule provided for analysis")
        if not analysis["has_weather_alert"]:
            analysis["recommended_next_agent"] = "crew_ops"
    
    # Check for flight cancellation
    flight_cancellation = state.get("flight_cancellation_notification")
    if flight_cancellation:
        analysis["has_flight_cancellation"] = True
        analysis["priority_issues"].append("Flight cancellation detected")
    
    # Determine final recommendation
    if analysis["has_weather_alert"]:
        analysis["recommended_next_agent"] = "dispatch_ops"
        analysis["analysis_summary"] = "Weather alert detected - dispatch should assess weather first, then crew issues"
    elif analysis["has_crew_issues"]:
        analysis["recommended_next_agent"] = "crew_ops"
        analysis["analysis_summary"] = "Crew issues detected - crew ops should address FAA compliance"
    elif analysis["has_flight_cancellation"]:
        analysis["recommended_next_agent"] = "passenger_rebooking"
        analysis["analysis_summary"] = "Flight cancellation detected - passenger rebooking needed"
    else:
        analysis["recommended_next_agent"] = "crew_ops"
        analysis["analysis_summary"] = "No specific issues detected - default to crew ops for general assessment"
    
    return analysis

@tool
def determine_workflow_sequence_tool(initial_analysis: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determines the optimal workflow sequence based on initial analysis and current state.
    
    Args:
        initial_analysis: Results from analyze_initial_state_tool
        current_state: Current system state
        
    Returns:
        Dictionary with workflow sequence and routing logic
    """
    workflow = {
        "sequence": [],
        "current_step": 0,
        "next_agent": "",
        "workflow_complete": False,
        "routing_logic": ""
    }
    
    has_weather = initial_analysis.get("has_weather_alert", False)
    has_crew_issues = initial_analysis.get("has_crew_issues", False)
    has_cancellation = initial_analysis.get("has_flight_cancellation", False)
    
    # Build workflow sequence based on conditions
    if has_weather:
        workflow["sequence"] = ["dispatch_ops", "crew_ops"]
        workflow["routing_logic"] = "Weather alert → Dispatch assesses weather → Crew ops addresses any crew issues"
    elif has_crew_issues:
        workflow["sequence"] = ["crew_ops"]
        workflow["routing_logic"] = "Crew issues → Crew ops addresses FAA compliance"
    else:
        workflow["sequence"] = ["crew_ops"]
        workflow["routing_logic"] = "Default → Crew ops for general assessment"
    
    # Add passenger rebooking if there's a cancellation
    if has_cancellation:
        workflow["sequence"].extend(["passenger_rebooking", "confirmation", "database_update"])
        workflow["routing_logic"] += " → Passenger rebooking for cancellations"
    
    # Always end with planner for summary
    workflow["sequence"].append("planner")
    
    # Determine next agent
    if workflow["sequence"]:
        workflow["next_agent"] = workflow["sequence"][0]
    
    return workflow

@tool
def check_agent_completion_status_tool(state: Dict[str, Any], expected_agent: str) -> Dict[str, Any]:
    """
    Checks if the expected agent has completed its work and determines the next step.
    
    Args:
        state: Current system state
        expected_agent: The agent that should have completed its work
        
    Returns:
        Dictionary with completion status and next routing decision
    """
    status = {
        "agent_completed": False,
        "next_agent": "",
        "completion_evidence": [],
        "remaining_issues": []
    }
    
    # Check for agent-specific completion indicators
    if expected_agent == "dispatch_ops":
        dispatch_status = state.get("dispatch_status")
        if dispatch_status:
            status["agent_completed"] = True
            status["completion_evidence"].append(f"Dispatch status: {dispatch_status}")
            
            # Check if crew issues need to be addressed
            crew_legality_status = state.get("crew_legality_status")
            if crew_legality_status == "EXCEPTION":
                status["remaining_issues"].append("Crew legality violations need resolution")
                status["next_agent"] = "crew_ops"
            else:
                status["next_agent"] = "passenger_rebooking" if state.get("flight_cancellation_notification") else "planner"
    
    elif expected_agent == "crew_ops":
        crew_substitutions = state.get("crew_substitutions", {})
        legality_flags = state.get("legality_flags", [])
        
        if crew_substitutions or not legality_flags:
            status["agent_completed"] = True
            status["completion_evidence"].append(f"Crew substitutions: {len(crew_substitutions)}")
            status["next_agent"] = "passenger_rebooking" if state.get("flight_cancellation_notification") else "planner"
        else:
            status["remaining_issues"].append("Crew violations still need resolution")
    
    elif expected_agent == "passenger_rebooking":
        rebooking_proposals = state.get("rebooking_proposals", [])
        if rebooking_proposals:
            status["agent_completed"] = True
            status["completion_evidence"].append(f"Rebooking proposals: {len(rebooking_proposals)}")
            status["next_agent"] = "confirmation"
    
    elif expected_agent == "confirmation":
        confirmations = state.get("confirmations", [])
        if confirmations:
            status["agent_completed"] = True
            status["completion_evidence"].append(f"Confirmations: {len(confirmations)}")
            status["next_agent"] = "database_update"
    
    elif expected_agent == "database_update":
        # Check if database updates were processed
        messages = state.get("messages", [])
        db_update_messages = [msg for msg in messages if "database" in msg.lower() and "update" in msg.lower()]
        if db_update_messages:
            status["agent_completed"] = True
            status["completion_evidence"].append("Database updates processed")
            status["next_agent"] = "planner"
    
    return status

@tool
def read_messages_tool(run_id: str = "default") -> str:
    """
    Reads all agent messages for a given run_id from the agent_logs table via MCP.

    Args:
        run_id (str): Unique identifier for this execution run (e.g., "UA-ops-2025-06-20")

    Returns:
        str: A formatted chronological log of all system messages for the run.
    """
    try:
        db_client = get_database_client_instance()
        
        # Use the database MCP client to read messages
        # Note: This would need to be implemented in the database MCP server
        # For now, we'll use a simple approach
        result = db_client.execute_tool("read_messages", {"run_id": run_id})
        
        if result.get("success"):
            return result.get("result", f"No messages found in database for run_id: {run_id}")
        else:
            return f"❌ Error fetching messages from DB: {result.get('error', 'Unknown error')}"

    except Exception as e:
        return f"❌ Error fetching messages from DB: {str(e)}"

def save_summary_to_markdown(summary_text: Union[str, List[str], dict], run_id: str = "default"):
    """
    Saves a clean executive summary (from Claude or string/list input) to a Markdown file.
    - Strips emoji
    - Normalizes section headers
    - Handles Claude-style dicts, strings, and lists

    Args:
        summary_text (Union[str, List[str], dict]): The summary content.
        run_id (str): Unique run ID used in the filename.
    """
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/summary_{run_id}.md"

    # Extract raw text
    if isinstance(summary_text, dict) and "text" in summary_text:
        summary_text = summary_text["text"]
    elif isinstance(summary_text, list):
        summary_text = "\n\n".join(str(p).strip() for p in summary_text)
    summary_text = str(summary_text).strip()

    # Normalize and clean
    summary_text = summary_text.replace("EXECUTIVE SUMMARY", "").replace("Executive Summary", "")
    summary_text = summary_text.replace("----------", "").replace("--------", "")
    summary_text = summary_text.strip()

    # Strip emojis (basic ASCII-friendly filter)
    summary_text = re.sub(r"[^\x00-\x7F]+", "", summary_text)

    # Promote section headers like "Major Actions Taken:" to proper Markdown
    summary_text = re.sub(r"(?m)^([A-Z][A-Za-z ]+):\s*$", r"## \1", summary_text)

    # Final document
    formatted = f"""# Executive Summary – Run ID: {run_id}

{summary_text}
"""

    with open(filename, "w") as f:
        f.write(formatted)

    print(f"\nExecutive Markdown summary saved to: {filename}")

def planner_agent(state: Dict[str, Any], run_id: str = "default") -> Dict[str, Any]:
    """
    Enhanced Planner Agent that can act as both an intelligent router and a summary generator.
    
    This agent:
    1. Analyzes the initial state to determine routing logic
    2. Can route to appropriate agents based on conditions
    3. Monitors agent completion and determines next steps
    4. Generates executive summaries when workflow is complete
    
    Args:
        state (Dict[str, Any]): Current system state
        run_id (str): Unique identifier for this execution run
        
    Returns:
        Updated state with routing decisions and/or plan summary
    """
    print("🧠 Enhanced Intelligent PlannerAgent activated")

    # Check if this is the initial call (no workflow sequence yet)
    if "workflow_sequence" not in state:
        print("🔍 Initial state analysis - determining workflow routing...")
        
        # Analyze initial state
        initial_analysis = analyze_initial_state_tool.invoke({"state": state})
        print(f"📋 Initial Analysis: {initial_analysis['analysis_summary']}")
        
        # Determine workflow sequence
        workflow_info = determine_workflow_sequence_tool.invoke({
            "initial_analysis": initial_analysis,
            "current_state": state
        })
        
        # Store workflow information in state
        state.update({
            "workflow_sequence": workflow_info["sequence"],
            "current_step": 0,
            "next_agent": workflow_info["next_agent"],
            "routing_logic": workflow_info["routing_logic"],
            "initial_analysis": initial_analysis,
            "workflow_complete": False
        })
        
        print(f"🔄 Workflow Sequence: {' → '.join(workflow_info['sequence'])}")
        print(f"🎯 Next Agent: {workflow_info['next_agent']}")
        
        # Return state with routing information
        state.setdefault("messages", []).append(f"PlannerAgent: Determined workflow sequence - {workflow_info['routing_logic']}")
        return state
    
    # Check if we're at the end of the workflow (planner should generate summary)
    current_step = state.get("current_step", 0)
    workflow_sequence = state.get("workflow_sequence", [])
    
    if current_step >= len(workflow_sequence) - 1:  # Last step is planner
        print("📋 Workflow complete - generating executive summary...")
        
        # Generate executive summary
        return generate_executive_summary(state, run_id)
    
    # Check completion status of current agent
    current_agent = workflow_sequence[current_step] if current_step < len(workflow_sequence) else "planner"
    completion_status = check_agent_completion_status_tool.invoke({
        "state": state,
        "expected_agent": current_agent
    })
    
    if completion_status["agent_completed"]:
        # Move to next step
        next_step = current_step + 1
        next_agent = workflow_sequence[next_step] if next_step < len(workflow_sequence) else "planner"
        
        state.update({
            "current_step": next_step,
            "next_agent": next_agent
        })
        
        print(f"✅ {current_agent} completed - routing to {next_agent}")
        state.setdefault("messages", []).append(f"PlannerAgent: {current_agent} completed, routing to {next_agent}")
        
    else:
        # Agent hasn't completed - stay with current agent
        print(f"⏳ {current_agent} still in progress - remaining issues: {completion_status['remaining_issues']}")
        state.setdefault("messages", []).append(f"PlannerAgent: {current_agent} still processing - {completion_status['remaining_issues']}")
    
    return state

def generate_executive_summary(state: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    """
    Generates the final executive summary when workflow is complete.
    """
    print("📋 Generating final executive summary...")
    
    # Prepare a formatted string for crew substitutions
    crew_subs = state.get("crew_substitutions", {})
    if crew_subs:
        resolution_steps = ["Crew Substitutions:"]
        for flight, crew in crew_subs.items():
            crew_list = ', '.join(crew) if crew else 'None'
            resolution_steps.append(f"- Flight {flight}: {crew_list}")
        resolution_steps_str = '\n'.join(resolution_steps)
    else:
        resolution_steps_str = "No crew substitutions were required."

    # Prepare a formatted string for delay advisories
    delay_advisories = state.get("delay_advisories", [])
    print(f"[DEBUG] Delay advisories in state: {delay_advisories}")
    if delay_advisories:
        advisories_str = "Published Delay Advisories:\n" + '\n'.join(f"- {adv}" for adv in delay_advisories)
        print(f"[DEBUG] Formatted advisories string: {advisories_str}")
    else:
        advisories_str = "No delay advisories were published."
        print(f"[DEBUG] No delay advisories found in state")
    
    print(f"[DEBUG] Final advisories string being sent to LLM: {advisories_str}")

    # Initialize the LLM agent
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    llm = ChatAnthropic(
        model_name="claude-3-5-sonnet-latest", 
        temperature=0.3, 
        timeout=60, 
        stop=None
    )
    
    tools = [read_messages_tool]

    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are an executive planner summarizing operational activity.\n"
         "Use `read_messages_tool` to access the system-wide activity log.\n"
         "Then provide a clear executive summary that includes:\n"
         "- Major actions taken by agents\n"
         "- Any remaining issues or risks\n"
         "- Recommended next steps or resolutions\n"
         "- Resolution Steps: List all crew substitutions made, using the following data:\n"
         f"{resolution_steps_str}\n"
         "- Published Delay Advisories: List all advisories published, using the following data:\n"
         f"{advisories_str}\n"
         "If no substitutions or advisories were made, state that explicitly."
        ),
        ("user", "{input}"),
        ("ai", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print(f"🧾 Using run_id = {run_id} to fetch messages from DB")

    # Get messages directly first to ensure we have the right run_id
    try:
        messages = read_messages_tool.invoke({"run_id": run_id})
        print(f"📋 Retrieved messages for run_id {run_id}: {len(messages)} characters")
    except Exception as e:
        print(f"⚠️ Failed to get messages: {e}")
        messages = f"No messages found for run_id: {run_id}"

    result = agent_executor.invoke({
        "input": f"Generate an executive-level summary of all actions and changes from system agents. Use the following message log:\n\n{messages}",
        "run_id": run_id
    })

    output = result.get("output", "No summary generated.")
    if isinstance(output, list) and all(isinstance(i, dict) and "text" in i for i in output):
        # Claude-style list of completions
        summary_text = "\n\n".join(i["text"].strip() for i in output)
    elif isinstance(output, dict) and "text" in output:
        summary_text = output["text"]
    else:
        summary_text = str(output)

    # Save and log
    save_summary_to_markdown(summary_text, run_id)
    state["plan_summary"] = summary_text
    state["workflow_complete"] = True
    state.setdefault("messages", []).append("Enhanced PlannerAgent generated executive summary.")

    print("\n📋 Executive Summary:\n")
    print(summary_text)

    # === Human-In-The-Loop Approval for Executive Summary ===
    print("\n📋 Final Executive Summary:")
    print(summary_text)

    approval = input("\nDo you approve this plan summary? (yes/no): ").strip().lower()
    if approval != "yes":
        print("❌ Plan rejected by human reviewer.")
        state['messages'].append("Human reviewer rejected the plan summary.")
    else:
        print("✅ Plan approved by human reviewer.")
        state['messages'].append("Human reviewer approved the plan summary.")

    return state

def test_planner_agent():
    """
    Test function for the planner agent
    """
    print("Testing planner agent...")
    
    # Sample state
    test_state = {
        "proposals": [
            {
                "agent": "CrewOpsAgent",
                "flight": "UA101",
                "action": "Substitution",
                "reason": "FAA violation"
            }
        ],
        "messages": [
            "CrewOpsAgent: Substituted crew for flight UA101",
            "DispatchOpsAgent: All checks passed"
        ]
    }
    
    # Test the planner agent
    result = planner_agent(test_state, run_id="test-run-001")
    
    print("\nTest Results:")
    print(f"Plan summary generated: {bool(result.get('plan_summary'))}")
    print(f"Messages: {result.get('messages', [])}")
    
    return result

if __name__ == "__main__":
    test_planner_agent() 