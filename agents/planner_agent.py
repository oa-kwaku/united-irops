import sqlite3
import os
import re
from typing import Dict, Any, Union, List
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_PATH = "../database/united_ops.db"

@tool
def read_messages_tool(run_id: str = "default") -> str:
    """
    Reads all agent messages for a given run_id from the agent_logs table in SQLite.

    Args:
        run_id (str): Unique identifier for this execution run (e.g., "UA-ops-2025-06-20")

    Returns:
        str: A formatted chronological log of all system messages for the run.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, agent_name, message
            FROM agent_logs
            WHERE run_id = ?
            ORDER BY timestamp ASC
        """, (run_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No messages found in database for run_id: {run_id}"

        return "\n".join(f"{ts} | {agent}: {msg}" for ts, agent, msg in rows)

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
    Planner agent that reads all logs from SQLite, generates an executive summary with Claude,
    updates the plan state, and saves a copy of the summary as a Markdown file.
    
    This agent:
    1. Reads all agent activity logs from the database
    2. Generates an executive summary using Claude
    3. Saves the summary to a Markdown file
    4. Updates the state with the plan summary
    5. Provides human-in-the-loop approval for the final plan
    
    Args:
        state (Dict[str, Any]): Current system state
        run_id (str): Unique identifier for this execution run
        
    Returns:
        Updated state with plan summary and approval status
    """
    print("🧠 Enhanced PlannerAgent activated")

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
         "- Recommended next steps or resolutions."),
        ("user", "{input}"),
        ("ai", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print(f"🧾 Using run_id = {run_id} to fetch messages from DB")

    result = agent_executor.invoke({
        "input": "Generate an executive-level summary of all actions and changes from system agents.",
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