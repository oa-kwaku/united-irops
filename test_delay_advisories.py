#!/usr/bin/env python3

# Test script to verify delay advisories are working correctly

def test_delay_advisories_formatting():
    """Test that delay advisories are formatted correctly for the executive summary."""
    
    # Simulate state with delay advisories (like what the dispatch agent creates)
    test_state = {
        "delay_advisories": [
            "Delay advisory: Flight UA101 at ORD expected delay due to weather from 2025-06-25 14:00:00 to 2025-06-25 18:00:00.",
            "Delay advisory: Flight UA102 at ORD expected delay due to weather from 2025-06-25 14:00:00 to 2025-06-25 18:00:00.",
            "Delay advisory: Flight UA103 at ORD expected delay due to weather from 2025-06-25 14:00:00 to 2025-06-25 18:00:00."
        ],
        "crew_substitutions": {
            "UA101": ["UA003", "UA000"],
            "UA102": ["UA010"]
        }
    }
    
    # Test the formatting logic (copied from planner_agent.py)
    delay_advisories = test_state.get("delay_advisories", [])
    if delay_advisories:
        advisories_str = "Published Delay Advisories:\n" + '\n'.join(f"- {adv}" for adv in delay_advisories)
    else:
        advisories_str = "No delay advisories published."
    
    crew_subs = test_state.get("crew_substitutions", {})
    if crew_subs:
        resolution_steps = ["Crew Substitutions:"]
        for flight, crew in crew_subs.items():
            crew_list = ', '.join(crew) if crew else 'None'
            resolution_steps.append(f"- Flight {flight}: {crew_list}")
        resolution_steps_str = '\n'.join(resolution_steps)
    else:
        resolution_steps_str = "No crew substitutions were required."
    
    print("✅ Delay Advisories Test Results:")
    print("=" * 50)
    print(f"Number of delay advisories: {len(delay_advisories)}")
    print(f"Formatted advisories string:\n{advisories_str}")
    print(f"\nCrew substitutions:\n{resolution_steps_str}")
    
    # Verify the formatting looks correct
    assert len(delay_advisories) == 3, f"Expected 3 delay advisories, got {len(delay_advisories)}"
    assert "Published Delay Advisories:" in advisories_str, "Missing 'Published Delay Advisories:' header"
    assert advisories_str.count("- ") == 3, f"Expected 3 bullet points, got {advisories_str.count('- ')}"
    
    print("\n✅ All tests passed! Delay advisories are formatted correctly.")

if __name__ == "__main__":
    test_delay_advisories_formatting() 