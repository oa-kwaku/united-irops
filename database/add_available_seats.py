import pandas as pd
import random

def add_available_seats():
    """
    Add available_seats column to cleaned_flights.csv with random numbers between 1 and 10
    """
    print("Adding available_seats column to cleaned_flights.csv...")
    
    # Read the current flights data
    flights_df = pd.read_csv("database/united_ops/cleaned_flights.csv")
    
    print(f"Current shape: {flights_df.shape}")
    print(f"Current columns: {list(flights_df.columns)}")
    
    # Add available_seats column with random numbers between 1 and 10
    flights_df['available_seats'] = [random.randint(1, 10) for _ in range(len(flights_df))]
    
    print(f"New shape: {flights_df.shape}")
    print(f"New columns: {list(flights_df.columns)}")
    
    # Show sample of the new column
    print("\nSample of available_seats column:")
    print(flights_df[['flight_number', 'available_seats']].head(10))
    
    # Show statistics of available seats
    print(f"\nAvailable seats statistics:")
    print(f"Mean: {flights_df['available_seats'].mean():.2f}")
    print(f"Min: {flights_df['available_seats'].min()}")
    print(f"Max: {flights_df['available_seats'].max()}")
    print(f"Distribution:")
    print(flights_df['available_seats'].value_counts().sort_index())
    
    # Save the updated file
    flights_df.to_csv("database/united_ops/cleaned_flights.csv", index=False)
    
    print(f"\n✅ Successfully added available_seats column to cleaned_flights.csv")
    
    return flights_df

if __name__ == "__main__":
    add_available_seats() 