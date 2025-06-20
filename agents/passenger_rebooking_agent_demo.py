"""
Demonstration of the Passenger Rebooking Agent Integration

This script shows how to integrate the updated passenger rebooking agent
with the existing LangGraph system to handle flight cancellation notifications.
"""

import pandas as pd
import sqlite3
from typing import Dict, Any, List
from datetime import datetime

# Import the existing agent structure (simplified version)
class SystemState:
    def __init__(self):
        self.proposals = []
        self.messages = []
        self.impacted_passengers = None
        self.alternative_flights = None
        self.rebooking_proposals = None

def find_alternative_flights(cancelled_flight_number: str, departure_location: str, arrival_location: str, cancelled_departure_time: str) -> pd.DataFrame:
    """
    Find alternative flights with the same origin and destination with departure times later than the cancelled flight.
    """
    conn = sqlite3.connect("database/united_ops.db")
    
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
        is_international
    FROM flights 
    WHERE departure_location = ?
    AND arrival_location = ?
    AND departure_time > ?
    AND flight_number != ?
    AND status != 'cancelled'
    ORDER BY departure_time ASC
    """
    
    alternative_flights_df = pd.read_sql_query(
        alternative_flights_query,
        conn,
        params=[departure_location, arrival_location, cancelled_departure_time, cancelled_flight_number]
    )
    
    # Convert time columns to datetime for easier manipulation
    alternative_flights_df['departure_time'] = pd.to_datetime(alternative_flights_df['departure_time'])
    alternative_flights_df['arrival_time'] = pd.to_datetime(alternative_flights_df['arrival_time'])
    
    conn.close()
    
    return alternative_flights_df

def passenger_rebooking_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updated Passenger Rebooking Agent that handles flight cancellation notifications.
    
    When a flight cancellation notification is present in the state, this agent:
    1. Extracts the cancelled flight details (flight_number, arrival_location, arrival_time)
    2. Queries the database to find all passengers on the cancelled flight
    3. Creates a dataframe with passenger_id, loyalty_tier, and empty new_flight column
    4. Finds alternative flights to the same destination with later departure times
    5. Generates rebooking proposals for each impacted passenger
    """
    print("🧑‍💼 PassengerRebookingAgent activated")
    
    if "messages" not in state:
        state["messages"] = []
    state["messages"].append("PassengerRebookingAgent reviewed passenger disruptions")
    
    # Check for flight cancellation notification in the state
    flight_cancellation = state.get("flight_cancellation_notification")
    
    if flight_cancellation:
        # Extract cancellation details
        cancelled_flight_number = flight_cancellation.get("flight_number")
        arrival_location = flight_cancellation.get("arrival_location")
        arrival_time = flight_cancellation.get("arrival_time")
        
        print(f"🚨 Flight cancellation detected: {cancelled_flight_number} to {arrival_location}")
        
        # Query database for all passengers on the cancelled flight
        conn = sqlite3.connect("database/united_ops.db")
        
        # Get all passengers on the cancelled flight with their loyalty tiers
        impacted_passengers_query = """
        SELECT passenger_id, loyalty_tier
        FROM passengers 
        WHERE flight_number = ?
        """
        
        impacted_passengers_df = pd.read_sql_query(
            impacted_passengers_query, 
            conn, 
            params=[cancelled_flight_number]
        )
        
        # Add empty new_flight column
        impacted_passengers_df['new_flight'] = ''
        
        # Get the cancelled flight's departure time for finding alternatives
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
        
        if not cancelled_flight_info.empty:
            cancelled_departure_time = cancelled_flight_info.iloc[0]['departure_time']
            cancelled_departure_location = cancelled_flight_info.iloc[0]['departure_location']
            
            # Find alternative flights
            alternative_flights_df = find_alternative_flights(
                cancelled_flight_number, 
                cancelled_departure_location,
                arrival_location, 
                cancelled_departure_time
            )
            
            print(f"📊 Found {len(impacted_passengers_df)} impacted passengers")
            print(f"Impacted passengers preview:")
            print(impacted_passengers_df.head())
            
            print(f"✈️ Found {len(alternative_flights_df)} alternative flights to {arrival_location}")
            print(f"Alternative flights preview:")
            print(alternative_flights_df[['flight_number', 'departure_location', 'departure_time', 'arrival_time', 'status']].head())
            
            # Store both dataframes in state
            state["impacted_passengers"] = impacted_passengers_df
            state["alternative_flights"] = alternative_flights_df
            
            # Create rebooking proposals (placeholder for now)
            proposals = []
            for _, row in impacted_passengers_df.iterrows():
                proposals.append({
                    "passenger_id": row["passenger_id"],
                    "original_flight": cancelled_flight_number,
                    "loyalty_tier": row["loyalty_tier"],
                    "rebooked_flight": "",  # Will be filled by rebooking logic
                    "arrival_location": arrival_location,
                    "arrival_time": arrival_time,
                    "alternative_flights_available": len(alternative_flights_df)
                })
            
            return {
                **state,
                "proposals": state["proposals"] + [{"PassengerRebookingAgent": proposals}],
                "rebooking_proposals": proposals
            }
        else:
            print(f"❌ Could not find departure time for cancelled flight {cancelled_flight_number}")
            return {
                **state,
                "proposals": state["proposals"] + [{"PassengerRebookingAgent": []}],
                "rebooking_proposals": []
            }
    else:
        # Original stub logic for other passenger disruptions
        print("No flight cancellation notification found, using original logic")
        return {
            **state,
            "proposals": state["proposals"] + [{"PassengerRebookingAgent": []}],
            "rebooking_proposals": []
        }

def demonstrate_integration():
    """
    Demonstrate how the passenger rebooking agent integrates with the LangGraph system
    """
    print("=" * 60)
    print("PASSENGER REBOOKING AGENT INTEGRATION DEMONSTRATION")
    print("=" * 60)
    
    # Scenario 1: Flight cancellation notification
    print("\n📋 SCENARIO 1: Flight Cancellation Notification")
    print("-" * 40)
    
    # Create a flight cancellation notification (as would be created by planner agent)
    flight_cancellation_notification = {
        "flight_number": "DL7016",
        "arrival_location": "ORD",
        "arrival_time": "2025-06-25 07:36:00"
    }
    
    # Initial state with cancellation notification
    initial_state = {
        "proposals": [],
        "messages": [],
        "flight_cancellation_notification": flight_cancellation_notification
    }
    
    print(f"Initial state contains flight cancellation notification:")
    print(f"  Flight: {flight_cancellation_notification['flight_number']}")
    print(f"  Destination: {flight_cancellation_notification['arrival_location']}")
    print(f"  Arrival Time: {flight_cancellation_notification['arrival_time']}")
    
    # Run the passenger rebooking agent
    result = passenger_rebooking_agent(initial_state)
    
    print(f"\n✅ Agent Results:")
    print(f"  Messages: {len(result['messages'])}")
    print(f"  Impacted passengers: {len(result.get('impacted_passengers', pd.DataFrame()))}")
    print(f"  Alternative flights: {len(result.get('alternative_flights', pd.DataFrame()))}")
    print(f"  Rebooking proposals: {len(result.get('rebooking_proposals', []))}")
    
    # Show sample of impacted passengers dataframe
    if result.get('impacted_passengers') is not None:
        print(f"\n📊 Impacted Passengers Dataframe:")
        print(result['impacted_passengers'].head())
    
    # Show sample of alternative flights dataframe
    if result.get('alternative_flights') is not None:
        print(f"\n✈️ Alternative Flights Dataframe (Sample):")
        alt_flights_sample = result['alternative_flights'][['flight_number', 'departure_location', 'departure_time', 'arrival_time', 'status']].head(5)
        print(alt_flights_sample.to_string(index=False))
        
        # Show analysis
        print(f"\n📊 Alternative Flights Analysis:")
        print(f"  Total alternatives: {len(result['alternative_flights'])}")
        print(f"  From same origin (JFK): {len(result['alternative_flights'][result['alternative_flights']['departure_location'] == 'JFK'])}")
        print(f"  Scheduled flights: {len(result['alternative_flights'][result['alternative_flights']['status'] == 'scheduled'])}")
        print(f"  Delayed flights: {len(result['alternative_flights'][result['alternative_flights']['status'] == 'delayed'])}")
    
    # Show sample rebooking proposal
    if result.get('rebooking_proposals'):
        print(f"\n📋 Sample Rebooking Proposal:")
        print(result['rebooking_proposals'][0])
    
    # Scenario 2: No cancellation notification (original logic)
    print("\n\n📋 SCENARIO 2: No Flight Cancellation (Original Logic)")
    print("-" * 40)
    
    initial_state_no_cancellation = {
        "proposals": [],
        "messages": []
    }
    
    result_no_cancellation = passenger_rebooking_agent(initial_state_no_cancellation)
    
    print(f"✅ Agent Results (no cancellation):")
    print(f"  Messages: {len(result_no_cancellation['messages'])}")
    print(f"  Rebooking proposals: {len(result_no_cancellation.get('rebooking_proposals', []))}")
    
    print("\n" + "=" * 60)
    print("INTEGRATION DEMONSTRATION COMPLETE")
    print("=" * 60)

def show_usage_instructions():
    """
    Show instructions for integrating this into the Jupyter notebook
    """
    print("\n" + "=" * 60)
    print("INTEGRATION INSTRUCTIONS FOR JUPYTER NOTEBOOK")
    print("=" * 60)
    
    print("""
To integrate this updated passenger rebooking agent into your Jupyter notebook:

1. ADD the find_alternative_flights function before the passenger_rebooking_agent:

def find_alternative_flights(cancelled_flight_number: str, departure_location: str, arrival_location: str, cancelled_departure_time: str) -> pd.DataFrame:
    '''
    Find alternative flights with the same origin and destination with departure times later than the cancelled flight.
    '''
    conn = sqlite3.connect("../database/united_ops.db")
    
    alternative_flights_query = '''
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
        is_international
    FROM flights 
    WHERE departure_location = ?
    AND arrival_location = ?
    AND departure_time > ?
    AND flight_number != ?
    AND status != 'cancelled'
    ORDER BY departure_time ASC
    '''
    
    alternative_flights_df = pd.read_sql_query(
        alternative_flights_query,
        conn,
        params=[departure_location, arrival_location, cancelled_departure_time, cancelled_flight_number]
    )
    
    # Convert time columns to datetime for easier manipulation
    alternative_flights_df['departure_time'] = pd.to_datetime(alternative_flights_df['departure_time'])
    alternative_flights_df['arrival_time'] = pd.to_datetime(alternative_flights_df['arrival_time'])
    
    conn.close()
    
    return alternative_flights_df

2. REPLACE the existing passenger_rebooking_agent function in Cell 12 with:

def passenger_rebooking_agent(state: SystemState) -> SystemState:
    print("🧑‍💼 PassengerRebookingAgent activated")
    if "messages" not in state:
        state["messages"] = []
    state["messages"].append("PassengerRebookingAgent reviewed passenger disruptions")
    
    # Check for flight cancellation notification in the state
    flight_cancellation = state.get("flight_cancellation_notification")
    
    if flight_cancellation:
        # Extract cancellation details
        cancelled_flight_number = flight_cancellation.get("flight_number")
        arrival_location = flight_cancellation.get("arrival_location")
        arrival_time = flight_cancellation.get("arrival_time")
        
        print(f"🚨 Flight cancellation detected: {cancelled_flight_number} to {arrival_location}")
        
        # Query database for all passengers on the cancelled flight
        conn = sqlite3.connect("../database/united_ops.db")
        
        # Get all passengers on the cancelled flight with their loyalty tiers
        impacted_passengers_query = '''
        SELECT passenger_id, loyalty_tier
        FROM passengers 
        WHERE flight_number = ?
        '''
        
        impacted_passengers_df = pd.read_sql_query(
            impacted_passengers_query, 
            conn, 
            params=[cancelled_flight_number]
        )
        
        # Add empty new_flight column
        impacted_passengers_df['new_flight'] = ''
        
        # Get the cancelled flight's departure time for finding alternatives
        cancelled_flight_query = '''
        SELECT departure_time, departure_location
        FROM flights
        WHERE flight_number = ?
        '''
        
        cancelled_flight_info = pd.read_sql_query(
            cancelled_flight_query,
            conn,
            params=[cancelled_flight_number]
        )
        
        conn.close()
        
        if not cancelled_flight_info.empty:
            cancelled_departure_time = cancelled_flight_info.iloc[0]['departure_time']
            cancelled_departure_location = cancelled_flight_info.iloc[0]['departure_location']
            
            # Find alternative flights
            alternative_flights_df = find_alternative_flights(
                cancelled_flight_number, 
                cancelled_departure_location,
                arrival_location, 
                cancelled_departure_time
            )
            
            print(f"📊 Found {len(impacted_passengers_df)} impacted passengers")
            print(f"✈️ Found {len(alternative_flights_df)} alternative flights to {arrival_location}")
            
            # Store both dataframes in state
            state["impacted_passengers"] = impacted_passengers_df
            state["alternative_flights"] = alternative_flights_df
            
            # Create rebooking proposals
            proposals = []
            for _, row in impacted_passengers_df.iterrows():
                proposals.append({
                    "passenger_id": row["passenger_id"],
                    "original_flight": cancelled_flight_number,
                    "loyalty_tier": row["loyalty_tier"],
                    "rebooked_flight": "",  # Will be filled by rebooking logic
                    "arrival_location": arrival_location,
                    "arrival_time": arrival_time,
                    "alternative_flights_available": len(alternative_flights_df)
                })
            
            return {
                **state,
                "proposals": state["proposals"] + [{"PassengerRebookingAgent": proposals}],
                "rebooking_proposals": proposals
            }
        else:
            print(f"❌ Could not find departure time for cancelled flight {cancelled_flight_number}")
            return {
                **state,
                "proposals": state["proposals"] + [{"PassengerRebookingAgent": []}],
                "rebooking_proposals": []
            }
    else:
        # Original stub logic for other passenger disruptions
        itinerary = state.get("passenger_itinerary", pd.DataFrame())
        affected = []
        proposals = []
        for idx, row in itinerary.iterrows():
            if row.get("status") == "cancelled" or row.get("missed_connection", False):
                affected.append(row["passenger_id"])
                # Stub: propose a new flight (just append '_rebooked' to flight_id)
                proposals.append({
                    "passenger_id": row["passenger_id"],
                    "original_flight": row["flight_id"],
                    "rebooked_flight": f"{row['flight_id']}_rebooked"
                })
        return {
            **state,
            "proposals": state["proposals"] + [{"PassengerRebookingAgent": proposals}],
            "rebooking_proposals": proposals
        }

3. ADD a test cell to demonstrate the functionality:

# Test flight cancellation functionality with alternative flights
test_cancellation = {
    "flight_number": "DL7016",
    "arrival_location": "ORD", 
    "arrival_time": "2025-06-25 07:36:00"
}

test_state = {
    "proposals": [],
    "crew_schedule": mock_crew_schedule,
    "passenger_itinerary": mock_passenger_itinerary,
    "flight_cancellation_notification": test_cancellation
}

result = passenger_rebooking_agent(test_state)
print("Impacted passengers:", result.get('impacted_passengers', 'Not found'))
print("Alternative flights:", result.get('alternative_flights', 'Not found'))
print("Rebooking proposals:", len(result.get('rebooking_proposals', [])))
""")

if __name__ == "__main__":
    demonstrate_integration()
    show_usage_instructions() 