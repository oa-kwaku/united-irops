import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Simple state for testing
class TestState(TypedDict):
    messages: list
    step: int

def test_simple_langgraph():
    """Simple test to verify LangGraph is working"""
    print("🧪 Testing LangGraph Setup...")
    
    # Create a simple graph
    workflow = StateGraph(TestState)
    
    def node_a(state: TestState) -> TestState:
        print("Node A executed")
        state["messages"].append("Node A")
        state["step"] = 1
        return state
    
    def node_b(state: TestState) -> TestState:
        print("Node B executed")
        state["messages"].append("Node B")
        state["step"] = 2
        return state
    
    def routing_decision(state: TestState) -> str:
        if state["step"] == 0:
            return "node_a"
        elif state["step"] == 1:
            return "node_b"
        else:
            return "end"
    
    # Add nodes
    workflow.add_node("node_a", node_a)
    workflow.add_node("node_b", node_b)
    # No routing node
    
    # Set entry point using START and conditional edges
    workflow.add_conditional_edges(
        START,
        routing_decision,
        {
            "node_a": "node_a",
            "node_b": "node_b",
            "end": END
        }
    )
    workflow.add_edge("node_a", "node_b")  # To allow a->b
    workflow.add_edge("node_b", END)  # To allow b to end
    
    # Compile
    app = workflow.compile()
    
    # Test with initial state
    initial_state = {"messages": [], "step": 0}
    result = app.invoke(initial_state)
    
    print("✅ LangGraph test completed!")
    print(f"Final state: {result}")
    return result

if __name__ == "__main__":
    test_simple_langgraph() 