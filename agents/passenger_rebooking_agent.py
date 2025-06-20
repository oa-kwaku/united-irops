import pandas as pd
import sqlite3
from typing import Dict, Any, List
from datetime import datetime

def find_alternative_flights(cancelled_flight_number: str, departure_location: str, arrival_location: str, cancelled_departure_time: str, db_path: str = "database/united_ops.db") -> pd.DataFrame:
    """
    Find alternative flights with the same origin and destination with departure times later than the cancelled flight.
    
    Args:
        cancelled_flight_number: The cancelled flight number
        departure_location: The origin airport code
        arrival_location: The destination airport code
        cancelled_departure_time: The departure time of the cancelled flight
        db_path: The path to the SQLite database
        
    Returns:
        DataFrame of alternative flights with relevant information including available seats
    """
    conn = sqlite3.connect(db_path)
    
    # Query for alternative flights with same origin and destination
    # Only include flights with departure time later than the cancelled flight
    # Exclude the cancelled flight itself and other cancelled flights
    # Include available_seats column for rebooking logic
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

def passenger_rebooking_agent(state: Dict[str, Any], db_path: str = "database/united_ops.db") -> Dict[str, Any]:
    """
    Passenger Rebooking Agent that handles flight cancellation notifications.
    
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
        conn = sqlite3.connect(db_path)
        
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
                cancelled_departure_time,
                db_path=db_path
            )
            
            print(f"📊 Found {len(impacted_passengers_df)} impacted passengers")
            print(f"Impacted passengers preview:")
            print(impacted_passengers_df.head())
            
            print(f"✈️ Found {len(alternative_flights_df)} alternative flights to {arrival_location}")
            print(f"Alternative flights preview:")
            print(alternative_flights_df[['flight_number', 'departure_location', 'departure_time', 'arrival_time', 'status', 'available_seats']].head())
            
            # Assign passengers to alternative flights
            assigned_passengers_df, updated_flights_df, assignment_summary = assign_passengers_to_flights(
                impacted_passengers_df, 
                alternative_flights_df
            )
            
            # Store both dataframes in state
            state["impacted_passengers"] = assigned_passengers_df
            state["alternative_flights"] = updated_flights_df
            state["assignment_summary"] = assignment_summary
            
            # Create rebooking proposals with assigned flights
            proposals = []
            for _, row in assigned_passengers_df.iterrows():
                proposal = {
                    "passenger_id": row["passenger_id"],
                    "original_flight": cancelled_flight_number,
                    "loyalty_tier": row["loyalty_tier"],
                    "rebooked_flight": row["new_flight"] if row["new_flight"] else "NO_FLIGHT_AVAILABLE",
                    "arrival_location": arrival_location,
                    "arrival_time": arrival_time,
                    "alternative_flights_available": len(alternative_flights_df),
                    "assignment_successful": bool(row["new_flight"])
                }
                
                # Add flight details if assigned
                if row["new_flight"]:
                    flight_info = updated_flights_df[updated_flights_df['flight_number'] == row["new_flight"]]
                    if not flight_info.empty:
                        flight = flight_info.iloc[0]
                        proposal.update({
                            "new_departure_time": flight['departure_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            "new_arrival_time": flight['arrival_time'].strftime('%Y-%m-%d %H:%M:%S'),
                            "new_gate": flight['gate'],
                            "remaining_seats": flight['available_seats']
                        })
                
                proposals.append(proposal)
            
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

def test_flight_cancellation():
    """
    Test function to demonstrate the flight cancellation functionality
    """
    print("Testing flight cancellation functionality...")
    
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
    
    # Test the passenger rebooking agent
    result = passenger_rebooking_agent(test_state)
    
    print("\nTest Results:")
    print(f"Impacted passengers dataframe shape: {result.get('impacted_passengers', pd.DataFrame()).shape}")
    print(f"Alternative flights dataframe shape: {result.get('alternative_flights', pd.DataFrame()).shape}")
    print(f"Number of rebooking proposals: {len(result.get('rebooking_proposals', []))}")
    
    # Show assignment summary if available
    if result.get('assignment_summary'):
        summary = result['assignment_summary']
        print(f"\n📊 Assignment Summary:")
        print(f"  Total passengers: {summary['total_passengers']}")
        print(f"  Successfully assigned: {summary['passengers_assigned']}")
        print(f"  Not assigned: {summary['passengers_not_assigned']}")
        print(f"  Assignment rate: {summary['assignment_rate']:.1f}%")
        print(f"  Flights used: {summary['flights_used']}")
        print(f"  Total seats used: {summary['total_seats_used']}")
    
    if result.get('rebooking_proposals'):
        print(f"\nSample proposal:")
        sample_proposal = result['rebooking_proposals'][0]
        for key, value in sample_proposal.items():
            print(f"  {key}: {value}")
    
    if result.get('impacted_passengers') is not None:
        print("\nImpacted passengers dataframe (with assignments):")
        print(result['impacted_passengers'][['passenger_id', 'loyalty_tier', 'new_flight']].head(10))
        
        # Show assignment statistics by loyalty tier
        if 'new_flight' in result['impacted_passengers'].columns:
            assigned = result['impacted_passengers'][result['impacted_passengers']['new_flight'] != '']
            not_assigned = result['impacted_passengers'][result['impacted_passengers']['new_flight'] == '']
            
            print(f"\nAssignment by loyalty tier:")
            for tier in ['1K', 'Gold', 'Silver', 'Premier', 'Basic']:
                tier_passengers = result['impacted_passengers'][result['impacted_passengers']['loyalty_tier'] == tier]
                tier_assigned = assigned[assigned['loyalty_tier'] == tier]
                if len(tier_passengers) > 0:
                    print(f"  {tier}: {len(tier_assigned)}/{len(tier_passengers)} assigned ({len(tier_assigned)/len(tier_passengers)*100:.1f}%)")
                else:
                    print(f"  {tier}: 0/0 assigned (0.0%)")
    
    if result.get('alternative_flights') is not None:
        print("\nAlternative flights dataframe (updated with seat usage):")
        # Get original alternative flights for comparison
        original_flights = find_alternative_flights("DL7016", "JFK", "ORD", "2025-06-25 03:56:00")
        used_flights = result['alternative_flights'][result['alternative_flights']['available_seats'] < original_flights['available_seats']]
        print(f"Flights with passengers assigned: {len(used_flights)}")
        if len(used_flights) > 0:
            print(used_flights[['flight_number', 'departure_time', 'available_seats']].head())
    
    return result

def assign_passengers_to_flights(impacted_passengers_df: pd.DataFrame, alternative_flights_df: pd.DataFrame) -> tuple:
    """
    Assign impacted passengers to alternative flights based on:
    1. Priority by loyalty tier (1K > Gold > Silver > Premier > Basic)
    2. Earliest available flight with open seats
    3. Update available seats as passengers are assigned
    
    Args:
        impacted_passengers_df: DataFrame with passenger_id, loyalty_tier, new_flight columns
        alternative_flights_df: DataFrame with flight information including available_seats
        
    Returns:
        tuple: (updated_passengers_df, updated_flights_df, assignment_summary)
    """
    # Create copies to avoid modifying original dataframes
    passengers_df = impacted_passengers_df.copy()
    flights_df = alternative_flights_df.copy()
    
    # Define loyalty tier priority (higher number = higher priority)
    loyalty_priority = {
        '1K': 5,
        'Platinum': 4,
        'Gold': 3,
        'Silver': 2, 
        'Basic': 1
    }
    
    # Add priority score to passengers
    passengers_df['priority_score'] = passengers_df['loyalty_tier'].map(loyalty_priority)
    
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
                    'departure_time': flight['departure_time'],
                    'remaining_seats': flight['available_seats'] - 1
                })
                
                print(f"  ✅ {passenger_id} ({loyalty_tier}) → {flight['flight_number']} (departs {flight['departure_time'].strftime('%H:%M')}, {flight['available_seats']-1} seats left)")
                assignments_made += 1
                assigned = True
                break
        
        if not assigned:
            print(f"  ❌ {passenger_id} ({loyalty_tier}) → NO FLIGHT AVAILABLE")
            passengers_not_assigned += 1
    
    # Create assignment summary
    assignment_summary = {
        'total_passengers': len(passengers_df),
        'passengers_assigned': assignments_made,
        'passengers_not_assigned': passengers_not_assigned,
        'assignment_rate': assignments_made / len(passengers_df) * 100,
        'flights_used': len(flights_df[flights_df['available_seats'] < alternative_flights_df['available_seats']]),
        'total_seats_used': alternative_flights_df['available_seats'].sum() - flights_df['available_seats'].sum(),
        'assignment_details': assignment_details
    }
    
    print(f"\n📊 Assignment Summary:")
    print(f"  Total passengers: {assignment_summary['total_passengers']}")
    print(f"  Successfully assigned: {assignment_summary['passengers_assigned']}")
    print(f"  Not assigned: {assignment_summary['passengers_not_assigned']}")
    print(f"  Assignment rate: {assignment_summary['assignment_rate']:.1f}%")
    print(f"  Flights used: {assignment_summary['flights_used']}")
    print(f"  Total seats used: {assignment_summary['total_seats_used']}")
    
    return passengers_df, flights_df, assignment_summary

if __name__ == "__main__":
    test_flight_cancellation() 