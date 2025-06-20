import sqlite3
import pandas as pd
import random

def update_database_with_seats():
    """
    Add available_seats column to the flights table in the database
    and populate it with data from the CSV file
    """
    print("Updating database with available_seats column...")
    
    # Connect to the database
    conn = sqlite3.connect("database/united_ops.db")
    
    # Read the updated CSV file with available_seats
    flights_df = pd.read_csv("database/united_ops/cleaned_flights.csv")
    
    print(f"CSV file shape: {flights_df.shape}")
    print(f"CSV columns: {list(flights_df.columns)}")
    
    # Check if available_seats column exists in database
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(flights)")
    columns = [column[1] for column in cursor.fetchall()]
    
    print(f"Current database columns: {columns}")
    
    if 'available_seats' not in columns:
        print("Adding available_seats column to database...")
        cursor.execute("ALTER TABLE flights ADD COLUMN available_seats INTEGER")
        print("✅ Added available_seats column to database")
    else:
        print("available_seats column already exists in database")
    
    # Update the database with the new data
    print("Updating database with new flight data including available_seats...")
    
    # Drop the existing table and recreate it with the new schema
    cursor.execute("DROP TABLE IF EXISTS flights")
    
    # Create the table with the new schema
    create_table_sql = """
    CREATE TABLE flights (
        flight_number TEXT,
        departure_location TEXT,
        arrival_location TEXT,
        departure_time TEXT,
        arrival_time TEXT,
        gate TEXT,
        status TEXT,
        crew_required INTEGER,
        flight_duration_minutes REAL,
        is_international INTEGER,
        available_seats INTEGER
    )
    """
    cursor.execute(create_table_sql)
    
    # Insert the data from CSV
    flights_df.to_sql('flights', conn, if_exists='replace', index=False)
    
    # Create index
    cursor.execute("CREATE INDEX idx_flights_flight_number ON flights(flight_number)")
    
    # Verify the update
    cursor.execute("SELECT COUNT(*) FROM flights")
    count = cursor.fetchone()[0]
    print(f"✅ Database updated successfully. Total flights: {count}")
    
    # Show sample data
    cursor.execute("SELECT flight_number, available_seats FROM flights LIMIT 5")
    sample_data = cursor.fetchall()
    print("Sample data from database:")
    for row in sample_data:
        print(f"  {row[0]}: {row[1]} seats")
    
    conn.commit()
    conn.close()
    
    print("✅ Database update completed successfully!")

if __name__ == "__main__":
    update_database_with_seats() 