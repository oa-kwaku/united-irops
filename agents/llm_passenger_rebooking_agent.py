import pandas as pd
from typing import Dict, Any, List
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
import os
from dotenv import load_dotenv
import sqlite3
from datetime import datetime
import inspect

# Load environment variables
load_dotenv()

@tool
def find_alternative_flights(cancelled_flight_number: str, departure_location: str, arrival_location: str, cancelled_departure_time: str, passenger_count: int = 10, db_path: str = "database/united_ops.db") -> List[Dict[str, Any]]:
    """
    Find alternative flights with the same origin and destination with departure times later than the cancelled flight.
    Builds the list dynamically until we have enough seats to accommodate all passengers, prioritized by earliest arrival time.
    
    Args:
        cancelled_flight_number: The cancelled flight number
        departure_location: The origin airport code
        arrival_location: The destination airport code
        cancelled_departure_time: The departure time of the cancelled flight
        passenger_count: Number of passengers to accommodate
        db_path: The path to the SQLite database
        
    Returns:
        List of dictionaries with alternative flight information including available seats
    """
    conn = sqlite3.connect(db_path)
    
    # Query for all alternative flights ordered by arrival time (earliest first)
    # We'll build the list dynamically until we have enough seats
    alternative_flights_query = """
    SELECT 
        flight_number,
        departure_location,
        arrival_location,
        departure_time,
        arrival_time,
        gate,
        status,
        crew_required,
        flight_duration_minutes,
        is_international,
        available_seats
    FROM flights 
    WHERE departure_location = ?
    AND arrival_location = ?
    AND departure_time > ?
    AND flight_number != ?
    AND status != 'cancelled'
    ORDER BY arrival_time ASC
    """
    
    all_alternative_flights_df = pd.read_sql_query(
        alternative_flights_query,
        conn,
        params=[departure_location, arrival_location, cancelled_departure_time, cancelled_flight_number]
    )
    
    # Convert time columns to datetime for easier manipulation
    all_alternative_flights_df['departure_time'] = pd.to_datetime(all_alternative_flights_df['departure_time'])
    all_alternative_flights_df['arrival_time'] = pd.to_datetime(all_alternative_flights_df['arrival_time'])
    
    conn.close()
    
    # Build the list dynamically until we have enough seats
    selected_flights = []
    total_seats_available = 0
    
    for _, flight in all_alternative_flights_df.iterrows():
        selected_flights.append(flight.to_dict())
        total_seats_available += flight['available_seats']
        
        # Stop when we have enough seats to accommodate all passengers
        if total_seats_available >= passenger_count:
            break
    
    print(f"📊 Found {len(selected_flights)} alternative flights with {total_seats_available} total seats for {passenger_count} passengers")
    print(f"   Earliest arrival: {selected_flights[0]['arrival_time'] if selected_flights else 'No flights'}")
    print(f"   Latest arrival: {selected_flights[-1]['arrival_time'] if selected_flights else 'No flights'}")
    
    return selected_flights

@tool
def get_impacted_passengers(cancelled_flight_number: str, db_path: str = "database/united_ops.db") -> List[Dict[str, Any]]:
    """
    Get all passengers on the cancelled flight with their loyalty tiers.
    Args:
        cancelled_flight_number: The flight number of the cancelled flight.
        db_path: Path to the database.
    Returns:
        List of dictionaries with passenger_id, name, and loyalty_tier.
    """
    conn = sqlite3.connect(db_path)
    impacted_passengers_query = """
    SELECT passenger_id, name, loyalty_tier
    FROM passengers 
    WHERE flight_number = ?
    """
    impacted_passengers_df = pd.read_sql_query(
        impacted_passengers_query, 
        conn, 
        params=[cancelled_flight_number]
    )
    conn.close()
    
    # Convert to list of dictionaries for serialization
    return impacted_passengers_df.to_dict('records')

@tool
def get_cancelled_flight_details(cancelled_flight_number: str, db_path: str = "database/united_ops.db") -> List[Dict[str, Any]]:
    """
    Get the cancelled flight's departure time and location.
    Args:
        cancelled_flight_number: The flight number of the cancelled flight.
        db_path: Path to the database.
    Returns:
        List of dictionaries with departure_time and departure_location.
    """
    conn = sqlite3.connect(db_path)
    cancelled_flight_query = """
    SELECT departure_time, departure_location
    FROM flights
    WHERE flight_number = ?
    """
    cancelled_flight_info = pd.read_sql_query(
        cancelled_flight_query,
        conn,
        params=[cancelled_flight_number]
    )
    conn.close()
    
    # Convert to list of dictionaries for serialization
    return cancelled_flight_info.to_dict('records')

@tool
def update_passenger_records(confirmations: List[Dict[str, Any]], db_path: str = "database/united_ops.db") -> int:
    """
    Processes passenger confirmations and updates the database for all passengers.
    - Accepted rebookings: Updates to new flight
    - Declined rebookings: Updates to UNASSIGNED status
    
    Args:
        confirmations: A list of confirmation dictionaries from the confirmation_agent.
        db_path: Path to the database.
    Returns:
        The number of passenger records updated.
    """
    if not confirmations:
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    updated_count = 0
    
    for conf in confirmations:
        passenger_id = conf['passenger_id']
        new_flight = conf['rebooked_flight']
        response = conf.get('response', '')
        
        try:
            cursor.execute("UPDATE passengers SET flight_number = ? WHERE passenger_id = ?", (new_flight, passenger_id))
            if cursor.rowcount > 0:
                updated_count += 1
                if response == "accept rebooking":
                    print(f"  - DB: Updated passenger {passenger_id} to flight {new_flight}")
                else:
                    print(f"  - DB: Updated passenger {passenger_id} to {new_flight} (declined rebooking)")
        except sqlite3.Error as e:
            print(f"  - DB ERROR for {passenger_id}: {e}")
    
    conn.commit()
    conn.close()
    print(f"  ✅ Committed {updated_count} updates to passenger records.")
    return updated_count

@tool
def assign_passengers_to_flights(impacted_passengers_data: List[Dict[str, Any]], alternative_flights_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Assign impacted passengers to alternative flights based on:
    1. Priority by loyalty tier (1K > Gold > Silver > Premier > Basic)
    2. Earliest available flight with open seats
    3. Update available seats as passengers are assigned
    
    Args:
        impacted_passengers_data: List of dictionaries with passenger_id, loyalty_tier, name
        alternative_flights_data: List of dictionaries with flight information including available_seats
        
    Returns:
        Dictionary with assignment results and summary
    """
    # Convert to DataFrames for processing
    passengers_df = pd.DataFrame(impacted_passengers_data)
    flights_df = pd.DataFrame(alternative_flights_data)
    
    # Add required columns
    passengers_df['new_flight'] = ''
    flights_df['departure_time'] = pd.to_datetime(flights_df['departure_time'])
    flights_df['arrival_time'] = pd.to_datetime(flights_df['arrival_time'])
    
    # Create copies to avoid modifying original dataframes
    passengers_df = passengers_df.copy()
    flights_df = flights_df.copy()
    
    # Define loyalty tier priority (higher number = higher priority)
    loyalty_priority = {
        '1K': 5,
        'Platinum': 4,
        'Gold': 3,
        'Silver': 2, 
        'Basic': 1
    }
    
    # Add priority score to passengers
    passengers_df['priority_score'] = passengers_df['loyalty_tier'].apply(lambda tier: loyalty_priority.get(tier, 0))
    
    # Sort passengers by priority (highest first) and then by passenger_id for consistency
    passengers_df = passengers_df.sort_values(['priority_score', 'passenger_id'], ascending=[False, True])
    
    # Sort flights by departure time (earliest first)
    flights_df = flights_df.sort_values('departure_time')
    
    # Track assignments
    assignments_made = 0
    passengers_not_assigned = 0
    assignment_details = []
    
    print(f"\n🔄 Assigning {len(passengers_df)} passengers to {len(flights_df)} alternative flights...")
    print(f"Priority order: {list(passengers_df['loyalty_tier'].value_counts().index)}")
    
    # Assign each passenger to the earliest available flight with seats
    for idx, passenger in passengers_df.iterrows():
        passenger_id = passenger['passenger_id']
        loyalty_tier = passenger['loyalty_tier']
        assigned = False
        
        # Find the earliest flight with available seats
        for flight_idx, flight in flights_df.iterrows():
            if flight['available_seats'] > 0:
                # Assign passenger to this flight
                passengers_df.loc[idx, 'new_flight'] = flight['flight_number']
                flights_df.loc[flight_idx, 'available_seats'] -= 1
                
                assignment_details.append({
                    'passenger_id': passenger_id,
                    'loyalty_tier': loyalty_tier,
                    'assigned_flight': flight['flight_number'],
                    'departure_time': str(flight['departure_time']),
                    'remaining_seats': flight['available_seats'] - 1
                })
                
                departure_time_str = pd.to_datetime(flight['departure_time']).strftime('%H:%M')
                print(f"  ✅ {passenger_id} ({loyalty_tier}) → {flight['flight_number']} (departs {departure_time_str}, {flight['available_seats']-1} seats left)")
                assignments_made += 1
                assigned = True
                break
        
        if not assigned:
            print(f"  ❌ {passenger_id} ({loyalty_tier}) → NO FLIGHT AVAILABLE")
            passengers_not_assigned += 1
    
    # Create assignment summary
    original_flights_df = pd.DataFrame(alternative_flights_data)
    
    # Calculate flights used by comparing original vs updated available seats
    flights_used = 0
    total_seats_used = 0
    
    for idx, flight in flights_df.iterrows():
        original_seats = original_flights_df.loc[original_flights_df['flight_number'] == flight['flight_number'], 'available_seats'].iloc[0]
        current_seats = flight['available_seats']
        seats_used = original_seats - current_seats
        if seats_used > 0:
            flights_used += 1
            total_seats_used += seats_used
    
    assignment_summary = {
        'total_passengers': len(passengers_df),
        'passengers_assigned': assignments_made,
        'passengers_not_assigned': passengers_not_assigned,
        'assignment_rate': assignments_made / len(passengers_df) * 100,
        'flights_used': flights_used,
        'total_seats_used': total_seats_used,
        'assignment_details': assignment_details
    }
    
    print(f"\n📊 Assignment Summary:")
    print(f"  Total passengers: {assignment_summary['total_passengers']}")
    print(f"  Successfully assigned: {assignment_summary['passengers_assigned']}")
    print(f"  Not assigned: {assignment_summary['passengers_not_assigned']}")
    print(f"  Assignment rate: {assignment_summary['assignment_rate']:.1f}%")
    print(f"  Flights used: {assignment_summary['flights_used']}")
    print(f"  Total seats used: {assignment_summary['total_seats_used']}")
    
    # Convert results back to serializable format
    return {
        'passengers': passengers_df.to_dict('records'),
        'flights': flights_df.to_dict('records'),
        'summary': assignment_summary
    }

@tool
def assign_passengers_from_state() -> Dict[str, Any]:
    """
    Assign impacted passengers to alternative flights using data stored in the current state.
    This tool reads passenger and flight data from the state and performs intelligent assignment.
    
    Returns:
        Dictionary with assignment results and summary
    """
    # This tool will be called by the LLM after data is stored in state
    # The actual assignment logic will be handled in the main function
    print("🔄 Assignment tool called - will use data from state")
    return {
        "status": "assignment_initiated",
        "message": "Assignment will be performed using data from state"
    }

def llm_passenger_rebooking_agent(state: Dict[str, Any], db_path: str = "database/united_ops.db") -> Dict[str, Any]:
    """
    LLM-powered Passenger Rebooking Agent that makes intelligent decisions about passenger rebooking.
    
    This agent uses Claude to:
    1. Analyze flight cancellation scenarios
    2. Make intelligent decisions about passenger assignments
    3. Handle edge cases and special circumstances
    4. Provide explanations for its decisions
    """
    print("🧠 LLM Passenger Rebooking Agent activated")
    
    if "messages" not in state:
        state["messages"] = []
    
    # Check for passenger confirmations to update the database
    if "confirmations" in state and state.get("confirmations"):
        print("📥 Processing passenger confirmations to update database...")
        confirmations = state.pop("confirmations")
        
        # Ensure we use the correct database path
        if not os.path.isabs(db_path):
            # Convert relative path to absolute path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, db_path)
        
        print(f"📁 Using database path: {db_path}")
        updated_count = update_passenger_records.invoke({"confirmations": confirmations, "db_path": db_path})
        state["messages"].append(f"LLM Passenger Rebooking Agent updated {updated_count} passenger records in the database.")
        return state

    # Check for flight cancellation notification
    flight_cancellation = state.get("flight_cancellation_notification")
    
    if not flight_cancellation:
        state["messages"].append("LLM Passenger Rebooking Agent: No flight cancellation detected")
        return state

    # Get flight details for agent input
    cancelled_flight_number = flight_cancellation.get("flight_number")
    arrival_location = flight_cancellation.get("arrival_location")

    # Initialize the LLM agent
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    # Set the API key as an environment variable for the ChatAnthropic class
    os.environ["ANTHROPIC_API_KEY"] = api_key
    
    llm = ChatAnthropic(
        model_name="claude-3-5-sonnet-latest", 
        temperature=0.1, 
        timeout=60, 
        stop=None
    )
    
    # Define the tools available to the agent
    tools = [
        find_alternative_flights,
        get_impacted_passengers,
        get_cancelled_flight_details,
        assign_passengers_from_state,
        update_passenger_records
    ]
    
    # Define the system prompt
    system_prompt = """You are an intelligent passenger rebooking agent for United Airlines. Your role is to:

1. ANALYZE flight cancellation situations and understand the impact
2. USE the available tools to gather information about:
   - Impacted passengers and their loyalty tiers
   - Cancelled flight details
   - Available alternative flights (dynamically selected based on passenger count)
3. INITIATE intelligent assignments using the assign_passengers_from_state tool
4. PROVIDE comprehensive analysis and explanations for your decisions

You have access to these tools:
- get_impacted_passengers: Find all passengers on a cancelled flight
- get_cancelled_flight_details: Get departure time and location of cancelled flight
- find_alternative_flights: Find available alternative flights (dynamically builds list until enough seats)
- assign_passengers_from_state: Perform intelligent passenger-to-flight assignments using data from state
- update_passenger_records: Update database after confirmations

Your workflow should be:
1. Call get_impacted_passengers to get passenger data
2. Call get_cancelled_flight_details to get flight details
3. Call find_alternative_flights to get alternative flights (provide passenger_count parameter)
4. Call assign_passengers_from_state to perform the assignment
5. Provide analysis and reasoning for your decisions

The data from your tool calls will be automatically stored in the state, and assign_passengers_from_state will use that data.

When using find_alternative_flights, provide the passenger_count parameter:
- The system will add flights one by one (earliest arrival first) until there are enough seats
- This ensures optimal flight selection while preventing token overflow
- You'll get the minimum number of flights needed to accommodate all passengers

Consider passenger loyalty tiers and preferences when making your analysis.
Always be thorough in your analysis and explain your reasoning clearly."""
    
    # Create the agent prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{input}"),
        ("ai", "{agent_scratchpad}")
    ])
    
    # Create the agent
    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)
    
    # Prepare the input for the agent
    print(f"🔍 About to create agent input for flight {cancelled_flight_number} to {arrival_location}")
    
    agent_input = f"""
    A flight cancellation has been detected:
    - Flight: {cancelled_flight_number}
    - Destination: {arrival_location}
    
    Please handle the passenger rebooking process by following these steps:
    
    1. First, get the impacted passengers using get_impacted_passengers
    2. Get the cancelled flight details using get_cancelled_flight_details  
    3. Find alternative flights using find_alternative_flights (provide passenger_count parameter)
    4. Make intelligent assignments using assign_passengers_from_state
    
    The data from your tool calls will be automatically stored in the state.
    Consider passenger loyalty tiers and preferences when making your analysis.
    Provide clear analysis and reasoning for your decisions.
    """
    
    print(f"🔍 About to execute agent with input length: {len(agent_input)}")
    
    try:
        print(f"🔍 Entering try block...")
        # Execute the agent
        result = agent_executor.invoke({"input": agent_input})
        print(f"🔍 Agent execution completed")
        
        # Extract the results from the agent's execution
        print("🤖 LLM Agent completed analysis")
        
        # Debug: Check the result structure
        print(f"🔍 Result type: {type(result)}")
        print(f"🔍 Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
        # Extract the LLM's output and tool calls
        llm_output = result.get("output", "")
        print(f"🤖 LLM Output: {llm_output}")
        
        # Debug: Check for intermediate_steps
        print(f"🔍 Has intermediate_steps: {'intermediate_steps' in result}")
        if 'intermediate_steps' in result:
            print(f"🔍 Intermediate steps length: {len(result['intermediate_steps'])}")
            print(f"🔍 Intermediate steps: {result['intermediate_steps']}")
        
        # Initialize variables to track extracted data
        assignment_results = None
        impacted_passengers_df = None
        alternative_flights_df = None
        cancelled_flight_info = None
        
        # Check if the LLM actually called the assignment tool
        # The result should contain the tool call results
        if 'intermediate_steps' in result and result['intermediate_steps']:
            print("🔍 Extracting LLM tool call results...")
            print(f"📋 LLM made {len(result['intermediate_steps'])} tool calls:")
            
            # Show all tool calls made by the LLM
            for i, step in enumerate(result['intermediate_steps']):
                if len(step) >= 2:
                    tool_name = step[0].tool if hasattr(step[0], 'tool') else str(step[0])
                    print(f"  {i+1}. {tool_name}")
            
            # Extract individual tool call results
            for step in result['intermediate_steps']:
                if len(step) >= 2:
                    tool_name = step[0].tool if hasattr(step[0], 'tool') else str(step[0])
                    tool_result = step[1]
                    tool_args = step[0].tool_input if hasattr(step[0], 'tool_input') else {}
                    
                    print(f"🔍 Tool call: {tool_name}")
                    print(f"   Args: {tool_args}")
                    print(f"   Result type: {type(tool_result)}")
                    print(f"   Result length: {len(tool_result) if hasattr(tool_result, '__len__') else 'N/A'}")
                    
                    # Store tool results in state
                    if tool_name == "get_impacted_passengers":
                        state["impacted_passengers_data"] = tool_result
                        print(f"✅ Stored {len(tool_result)} passengers in state")
                    elif tool_name == "find_alternative_flights":
                        state["alternative_flights_data"] = tool_result
                        print(f"✅ Stored {len(tool_result)} flights in state")
                    elif tool_name == "get_cancelled_flight_details":
                        state["cancelled_flight_info"] = tool_result
                        print(f"✅ Stored cancelled flight details in state")
                    elif tool_name == "assign_passengers_from_state":
                        print(f"🎯 LLM called assign_passengers_from_state!")
                        # Perform the actual assignment using data from state
                        assignment_results = assign_passengers_to_flights.invoke({
                            "impacted_passengers_data": state.get("impacted_passengers_data", []),
                            "alternative_flights_data": state.get("alternative_flights_data", [])
                        })
                        print(f"✅ Assignment completed using state data")
            
            # If LLM didn't call the assignment tool, we'll do it ourselves
            if not assignment_results:
                print("🔄 LLM didn't call assignment tool, performing assignment...")
                assignment_results = assign_passengers_to_flights.invoke({
                    "impacted_passengers_data": state.get("impacted_passengers_data", []),
                    "alternative_flights_data": state.get("alternative_flights_data", [])
                })
        else:
            print("❌ No intermediate steps found in LLM result")
            # Perform assignment using state data
            assignment_results = assign_passengers_to_flights.invoke({
                "impacted_passengers_data": state.get("impacted_passengers_data", []),
                "alternative_flights_data": state.get("alternative_flights_data", [])
            })
        
        # If we still don't have the necessary data, use fallback
        # Note: Data is now pre-loaded into state, so fallback is not needed
        
        # Get the cancelled flight details for proposal creation
        cancelled_flight_info = state.get("cancelled_flight_info", [])
        if not cancelled_flight_info:
            cancelled_flight_info = get_cancelled_flight_details.invoke({
                "cancelled_flight_number": cancelled_flight_number, 
                "db_path": db_path
            })
        
        cancelled_departure_time = cancelled_flight_info[0]['departure_time']
        cancelled_departure_location = cancelled_flight_info[0]['departure_location']
        
        # Create rebooking proposals with assigned flights
        proposals = []
        for passenger in assignment_results['passengers']:
            new_flight_value = str(passenger['new_flight']) if passenger['new_flight'] else ""
            
            proposal = {
                "passenger_id": passenger['passenger_id'],
                "passenger_name": passenger['name'],
                "original_flight": cancelled_flight_number,
                "loyalty_tier": passenger['loyalty_tier'],
                "rebooked_flight": new_flight_value if new_flight_value else "NO_FLIGHT_AVAILABLE",
                "departure_location": cancelled_departure_location,
                "arrival_location": arrival_location,
                "original_departure_time": cancelled_flight_info[0]['departure_time'],
                "alternative_flights_available": len(state.get("alternative_flights_data", [])),
                "assignment_successful": new_flight_value != ""
            }
            
            # Add flight details if assigned
            if new_flight_value:
                flight_info = [flight for flight in assignment_results['flights'] if flight['flight_number'] == new_flight_value]
                if len(flight_info) > 0:
                    flight = flight_info[0]
                    proposal.update({
                        "new_departure_time": flight['departure_time'],
                        "new_arrival_time": flight['arrival_time'],
                        "new_gate": flight['gate'],
                        "remaining_seats": flight['available_seats']
                    })
            
            proposals.append(proposal)
        
        state.update({
            "impacted_passengers": assignment_results['passengers'],
            "alternative_flights": assignment_results['flights'],
            "assignment_summary": assignment_results['summary'],
            "proposals": state.get("proposals", []) + [{"LLM_PassengerRebookingAgent": proposals}],
            "rebooking_proposals": proposals,
            "llm_analysis": llm_output,
            "llm_agent_result": result
        })
        
        state["messages"].append("LLM Passenger Rebooking Agent completed intelligent rebooking analysis")
        print(f"📊 Generated {len(proposals)} rebooking proposals")
        print(f"🤖 LLM Analysis: {llm_output[:200]}...")
        
    except Exception as e:
        print(f"❌ LLM Agent encountered an error: {e}")
        state["messages"].append(f"LLM Passenger Rebooking Agent error: {str(e)}")
        # Fallback to basic functionality
        state["messages"].append("Falling back to basic rebooking logic")
    
    return state

def test_llm_agent():
    """
    Test function for the LLM-powered passenger rebooking agent
    """
    print("Testing LLM-powered passenger rebooking agent...")
    
    # Sample flight cancellation notification
    test_cancellation = {
        "flight_number": "DL7016",
        "arrival_location": "ORD", 
        "arrival_time": "2025-06-25 07:36:00"
    }
    
    # Test state with cancellation notification
    test_state = {
        "proposals": [],
        "flight_cancellation_notification": test_cancellation
    }
    
    # Test the LLM passenger rebooking agent
    result = llm_passenger_rebooking_agent(test_state)
    
    print("\nTest Results:")
    print(f"Impacted passengers dataframe shape: {result.get('impacted_passengers', pd.DataFrame()).shape}")
    print(f"Alternative flights dataframe shape: {result.get('alternative_flights', pd.DataFrame()).shape}")
    print(f"Number of rebooking proposals: {len(result.get('rebooking_proposals', []))}")
    
    if result.get('llm_analysis'):
        print(f"\n🤖 LLM Analysis:")
        print(result['llm_analysis'])
    
    return result

if __name__ == "__main__":
    test_llm_agent() 