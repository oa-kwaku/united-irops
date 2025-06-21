import pandas as pd
from typing import Dict, Any, List
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
import os
from dotenv import load_dotenv
from datetime import datetime
import inspect
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
def find_alternative_flights(cancelled_flight_number: str, departure_location: str, arrival_location: str, cancelled_departure_time: str, passenger_count: int = 10) -> List[Dict[str, Any]]:
    """
    Find alternative flights with the same origin and destination with departure times later than the cancelled flight.
    Builds the list dynamically until we have enough seats to accommodate all passengers, prioritized by earliest arrival time.
    
    Args:
        cancelled_flight_number: The cancelled flight number
        departure_location: The origin airport code
        arrival_location: The destination airport code
        cancelled_departure_time: The departure time of the cancelled flight
        passenger_count: Number of passengers to accommodate
        
    Returns:
        List of dictionaries with alternative flight information including available seats
    """
    db_client = get_database_client_instance()
    
    # Query for all alternative flights ordered by arrival time (earliest first)
    # We'll build the list dynamically until we have enough seats
    alternative_flights = db_client.query_flights(
        departure_location=departure_location,
        arrival_location=arrival_location,
        limit=100  # Get a large batch to work with
    )
    
    # Filter flights that depart after the cancelled flight and are not cancelled
    filtered_flights = []
    for flight in alternative_flights:
        if (flight['departure_time'] > cancelled_departure_time and 
            flight['flight_number'] != cancelled_flight_number and 
            flight['status'] != 'cancelled'):
            filtered_flights.append(flight)
    
    # Sort by arrival time (earliest first)
    filtered_flights.sort(key=lambda x: x['arrival_time'])
    
    # Build the list dynamically until we have enough seats
    selected_flights = []
    total_seats_available = 0
    
    for flight in filtered_flights:
        selected_flights.append(flight)
        total_seats_available += flight['available_seats']
        
        # Stop when we have enough seats to accommodate all passengers
        if total_seats_available >= passenger_count:
            break
    
    return selected_flights

@tool
def get_impacted_passengers(cancelled_flight_number: str) -> List[Dict[str, Any]]:
    """
    Get all passengers on the cancelled flight with their loyalty tiers.
    Args:
        cancelled_flight_number: The flight number of the cancelled flight.
    Returns:
        List of dictionaries with passenger_id, name, and loyalty_tier.
    """
    db_client = get_database_client_instance()
    impacted_passengers = db_client.query_passengers(flight_number=cancelled_flight_number)
    
    # Convert to list of dictionaries for serialization
    return impacted_passengers

@tool
def get_cancelled_flight_details(cancelled_flight_number: str) -> List[Dict[str, Any]]:
    """
    Get the cancelled flight's departure time and location.
    Args:
        cancelled_flight_number: The flight number of the cancelled flight.
    Returns:
        List of dictionaries with departure_time and departure_location.
    """
    db_client = get_database_client_instance()
    flight_details = db_client.get_flight_details(cancelled_flight_number)
    
    if flight_details.get('success'):
        details = flight_details['details']
        return [{
            'departure_time': details['departure_time'],
            'departure_location': details['departure_location']
        }]
    else:
        return []

@tool
def update_passenger_records(confirmations: List[Dict[str, Any]]) -> int:
    """
    Processes passenger confirmations and updates the database for all passengers.
    - Accepted rebookings: Updates to new flight
    - Declined rebookings: Updates to UNASSIGNED status
    
    Args:
        confirmations: A list of confirmation dictionaries from the confirmation_agent.
    Returns:
        The number of passenger records updated.
    """
    if not confirmations:
        return 0

    db_client = get_database_client_instance()
    updated_count = 0
    
    for conf in confirmations:
        passenger_id = conf['passenger_id']
        new_flight = conf['rebooked_flight']
        response = conf.get('response', '')
        
        try:
            result = db_client.update_passenger_flight(
                passenger_id=passenger_id,
                new_flight=new_flight,
                reason=f"Rebooking confirmation: {response}"
            )
            
            if result.get('success'):
                updated_count += 1
            else:
                print(f"Database update failed for passenger {passenger_id}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"Database update error for passenger {passenger_id}: {e}")
    
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
    # Handle case when there are no passengers to assign
    if not impacted_passengers_data:
        return {
            'passengers': [],
            'flights': alternative_flights_data,
            'summary': {
                'total_passengers': 0,
                'passengers_assigned': 0,
                'passengers_not_assigned': 0,
                'assignment_rate': 0.0,
                'flights_used': 0,
                'total_seats_used': 0,
                'assignment_details': []
            }
        }
    
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
                
                assignments_made += 1
                assigned = True
                break
        
        if not assigned:
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
    return {
        "status": "assignment_initiated",
        "message": "Assignment will be performed using data from state"
    }

def llm_passenger_rebooking_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM-powered Passenger Rebooking Agent that makes intelligent decisions about passenger rebooking.
    
    This agent uses Claude to:
    1. Analyze flight cancellation scenarios
    2. Make intelligent decisions about passenger assignments
    3. Handle edge cases and special circumstances
    4. Provide explanations for its decisions
    """
    if "messages" not in state:
        state["messages"] = []
    
    # Check for passenger confirmations to update the database
    if "confirmations" in state and state.get("confirmations"):
        confirmations = state.pop("confirmations")
        
        updated_count = update_passenger_records.invoke({"confirmations": confirmations})
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
    
    try:
        # Execute the agent
        result = agent_executor.invoke({"input": agent_input})
        
        # Extract the results from the agent's execution
        llm_output = result.get("output", "")
        
        # Initialize variables to track extracted data
        assignment_results = None
        
        # Check if the LLM actually called the assignment tool
        # The result should contain the tool call results
        if 'intermediate_steps' in result and result['intermediate_steps']:
            # Extract individual tool call results
            for step in result['intermediate_steps']:
                if len(step) >= 2:
                    tool_name = step[0].tool if hasattr(step[0], 'tool') else str(step[0])
                    tool_result = step[1]
                    
                    # Store tool results in state
                    if tool_name == "get_impacted_passengers":
                        state["impacted_passengers_data"] = tool_result
                    elif tool_name == "find_alternative_flights":
                        state["alternative_flights_data"] = tool_result
                    elif tool_name == "get_cancelled_flight_details":
                        state["cancelled_flight_info"] = tool_result
                    elif tool_name == "assign_passengers_from_state":
                        # Perform the actual assignment using data from state
                        assignment_results = assign_passengers_to_flights.invoke({
                            "impacted_passengers_data": state.get("impacted_passengers_data", []),
                            "alternative_flights_data": state.get("alternative_flights_data", [])
                        })
            
            # If LLM didn't call the assignment tool, we'll do it ourselves
            if not assignment_results:
                assignment_results = assign_passengers_to_flights.invoke({
                    "impacted_passengers_data": state.get("impacted_passengers_data", []),
                    "alternative_flights_data": state.get("alternative_flights_data", [])
                })
        else:
            # Perform assignment using state data
            assignment_results = assign_passengers_to_flights.invoke({
                "impacted_passengers_data": state.get("impacted_passengers_data", []),
                "alternative_flights_data": state.get("alternative_flights_data", [])
            })
        
        # Get the cancelled flight details for proposal creation
        cancelled_flight_info = state.get("cancelled_flight_info", [])
        if not cancelled_flight_info:
            cancelled_flight_info = get_cancelled_flight_details.invoke({
                "cancelled_flight_number": cancelled_flight_number
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
        
    except Exception as e:
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
    print(f"Impacted passengers count: {len(result.get('impacted_passengers', []))}")
    print(f"Alternative flights count: {len(result.get('alternative_flights', []))}")
    print(f"Number of rebooking proposals: {len(result.get('rebooking_proposals', []))}")
    
    if result.get('llm_analysis'):
        print(f"\nLLM Analysis:")
        print(result['llm_analysis'])
    
    return result

if __name__ == "__main__":
    test_llm_agent() 