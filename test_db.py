import sqlite3
import os

# Test database connection
db_path = "database/united_ops.db"
print(f"Testing database: {db_path}")
print(f"Database exists: {os.path.exists(db_path)}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Test total crew count
    cursor.execute("SELECT COUNT(*) FROM crew")
    total_crew = cursor.fetchone()[0]
    print(f"Total crew in database: {total_crew}")
    
    # Test unassigned crew count
    cursor.execute("SELECT COUNT(*) FROM crew WHERE assigned_flight = 'UNASSIGNED'")
    unassigned_crew = cursor.fetchone()[0]
    print(f"Unassigned crew: {unassigned_crew}")
    
    # Test crew with rest hours >= 10
    cursor.execute("SELECT COUNT(*) FROM crew WHERE rest_hours_prior >= 10")
    rested_crew = cursor.fetchone()[0]
    print(f"Crew with rest hours >= 10: {rested_crew}")
    
    # Test crew with fatigue score <= 1.0
    cursor.execute("SELECT COUNT(*) FROM crew WHERE fatigue_score <= 1.0")
    low_fatigue_crew = cursor.fetchone()[0]
    print(f"Crew with fatigue score <= 1.0: {low_fatigue_crew}")
    
    # Test potential substitutes (unassigned + rested + low fatigue)
    cursor.execute("""
        SELECT COUNT(*) FROM crew 
        WHERE (assigned_flight IS NULL OR assigned_flight = 'UNASSIGNED')
        AND rest_hours_prior >= 10
        AND fatigue_score <= 1.0
    """)
    potential_substitutes = cursor.fetchone()[0]
    print(f"Potential substitutes: {potential_substitutes}")
    
    # Show sample unassigned crew
    if unassigned_crew > 0:
        cursor.execute("SELECT crew_id, name, role, rest_hours_prior, fatigue_score FROM crew WHERE assigned_flight = 'UNASSIGNED' LIMIT 3")
        sample_crew = cursor.fetchall()
        print("\nSample unassigned crew:")
        for crew in sample_crew:
            print(f"  - {crew[1]} ({crew[2]}) - Rest: {crew[3]:.1f}h, Fatigue: {crew[4]:.2f}")
    
    conn.close()
    print("\n✅ Database test completed successfully!")
    
except Exception as e:
    print(f"❌ Database test failed: {e}")
    import traceback
    traceback.print_exc() 