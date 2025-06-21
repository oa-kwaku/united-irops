import sqlite3
import pandas as pd
import os

def restore_database():
    """
    Restores the united_ops.db database from the CSV files in the united_ops folder.
    This function will drop existing tables and recreate them from the CSVs.
    """
    db_path = 'database/united_ops.db'
    csv_folder = 'database/united_ops'
    
    flights_csv = os.path.join(csv_folder, 'cleaned_flights.csv')
    passengers_csv = os.path.join(csv_folder, 'cleaned_passengers.csv')
    crew_csv = os.path.join(csv_folder, 'cleaned_crew.csv')

    # Check if all required CSVs exist
    for f in [flights_csv, passengers_csv, crew_csv]:
        if not os.path.exists(f):
            print(f"Error: Required CSV file not found at {f}")
            return
            
    print(f"Restoring database at {db_path}...")

    # Connect to the SQLite database (this will create it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- Table Schemas (inferred from CSVs and agent logic) ---
    
    # Flights table
    cursor.execute("DROP TABLE IF EXISTS flights")
    cursor.execute("""
    CREATE TABLE flights (
        flight_number TEXT PRIMARY KEY,
        departure_location TEXT,
        arrival_location TEXT,
        departure_time TEXT,
        arrival_time TEXT,
        gate TEXT,
        status TEXT,
        crew_required INTEGER,
        flight_duration_minutes INTEGER,
        is_international INTEGER,
        available_seats INTEGER
    )
    """)
    print("  - 'flights' table created.")

    # Passengers table
    cursor.execute("DROP TABLE IF EXISTS passengers")
    cursor.execute("""
    CREATE TABLE passengers (
        passenger_id TEXT PRIMARY KEY,
        name TEXT,
        flight_number TEXT,
        seat_number TEXT,
        loyalty_tier TEXT,
        has_precheck INTEGER,
        special_needs TEXT
    )
    """)
    print("  - 'passengers' table created.")
    
    # Crew table
    cursor.execute("DROP TABLE IF EXISTS crew")
    cursor.execute("""
    CREATE TABLE crew (
        crew_id TEXT PRIMARY KEY,
        name TEXT,
        assigned_flight TEXT,
        base TEXT,
        duty_start TEXT,
        duty_end TEXT,
        rest_hours_prior REAL,
        last_flight_end TEXT,
        fatigue_score REAL,
        role TEXT
    )
    """)
    print("  - 'crew' table created.")

    # --- Load data from CSVs into tables ---
    try:
        flights_df = pd.read_csv(flights_csv)
        flights_df.to_sql('flights', conn, if_exists='replace', index=False)
        print(f"  - Loaded {len(flights_df)} records into 'flights'.")
        
        passengers_df = pd.read_csv(passengers_csv)
        passengers_df.to_sql('passengers', conn, if_exists='replace', index=False)
        print(f"  - Loaded {len(passengers_df)} records into 'passengers'.")

        crew_df = pd.read_csv(crew_csv)
        crew_df.to_sql('crew', conn, if_exists='replace', index=False)
        print(f"  - Loaded {len(crew_df)} records into 'crew'.")
        
    except Exception as e:
        print(f"An error occurred while loading data: {e}")
        conn.close()
        return

    conn.commit()
    conn.close()
    
    print("\n✅ Database restoration complete.")

if __name__ == "__main__":
    restore_database() 