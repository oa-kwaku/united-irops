import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from typing import Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the agents
from agents.crew_ops_agent import crew_ops_agent
from agents.planner_agent import planner_agent

def test_crew_and_planner():
    """
    Test the crew ops and planner agents together to isolate issues.
    """
    print("🧪 Testing Crew Ops and Planner Agents Together")
    print("=" * 60)
    
    # Create a simple test state with crew schedule that has FAA violations
    test_state = {
        "run_id": f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "messages": [],
        # The crew ops agent will now query the database for the full schedule
    }
    
    print(f"📋 Test State:")
    print(f"  - Run ID: {test_state['run_id']}")
    print(f"  - Crew Schedule: Will be loaded from database by crew ops agent")
    print(f"  - Messages: {len(test_state.get('messages', []))}")
    
    print("\n" + "=" * 60)
    print("STEP 1: Testing Crew Operations Agent")
    print("=" * 60)
    
    try:
        # Test crew ops agent
        crew_result = crew_ops_agent(test_state)
        
        print(f"\n✅ Crew Ops Agent Results:")
        print(f"  - Crew substitutions: {len(crew_result.get('crew_substitutions', {}))}")
        print(f"  - Legality flags: {len(crew_result.get('legality_flags', []))}")
        print(f"  - Messages: {len(crew_result.get('messages', []))}")
        
        if crew_result.get('crew_substitutions'):
            print(f"  - Substitutions: {crew_result['crew_substitutions']}")
        
        if crew_result.get('legality_flags'):
            print(f"  - Violations: {crew_result['legality_flags']}")
        
        print(f"  - Final messages:")
        for msg in crew_result.get('messages', []):
            print(f"    - {msg}")
            
    except Exception as e:
        print(f"❌ Crew Ops Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("STEP 2: Testing Planner Agent")
    print("=" * 60)
    
    try:
        # Test planner agent
        planner_result = planner_agent(crew_result, run_id=test_state['run_id'])
        
        print(f"\n✅ Planner Agent Results:")
        print(f"  - Plan summary generated: {bool(planner_result.get('plan_summary'))}")
        print(f"  - Messages: {len(planner_result.get('messages', []))}")
        
        if planner_result.get('plan_summary'):
            print(f"  - Summary preview: {planner_result['plan_summary'][:200]}...")
        
        print(f"  - Final messages:")
        for msg in planner_result.get('messages', []):
            print(f"    - {msg}")
            
    except Exception as e:
        print(f"❌ Planner Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)

def test_crew_ops_only():
    """
    Test just the crew ops agent to debug database issues.
    """
    print("🧪 Testing Crew Ops Agent Only (Database Debug)")
    print("=" * 60)
    
    # Test with empty state to see database behavior
    empty_state = {
        "run_id": f"test-db-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "messages": []
    }
    
    print("📋 Testing with empty state (should query database)...")
    
    try:
        result = crew_ops_agent(empty_state)
        print(f"✅ Crew Ops with empty state completed")
        print(f"  - Messages: {len(result.get('messages', []))}")
        for msg in result.get('messages', []):
            print(f"    - {msg}")
    except Exception as e:
        print(f"❌ Crew Ops with empty state failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Check if API key is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No API key found in environment variables")
        print("Make sure your .env file contains: ANTHROPIC_API_KEY=your_key_here")
        exit(1)
    
    print(f"🔑 API Key loaded: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    
    # Run the main test
    test_crew_and_planner()
    
    # Uncomment to test database behavior
    # print("\n" + "=" * 60)
    # test_crew_ops_only() 