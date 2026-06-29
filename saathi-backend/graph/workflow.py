from langgraph.graph import StateGraph, END
from agents.supervisor import supervisor_node
from agents.life_event_predictor import predict_life_event
from agents.product_recommender import recommend_products
from agents.language_adapter import adapt_language
from agents.execution_builder import build_execution_payload
from graph.state import SAATHIState, ConversationStage

def route_after_supervisor(state: SAATHIState) -> str:
    """
    Supervisor decides next node based on incoming event type.
    """
    if state["stage"] == ConversationStage.TRIGGERED:
        return "life_event_predictor"
    elif state["stage"] == ConversationStage.LIFE_EVENT_IDENTIFIED:
        return "product_recommender"
    elif state["stage"] == ConversationStage.PRODUCT_RECOMMENDED:
        return "language_adapter"
    elif state["stage"] == ConversationStage.CONSENT_VERIFIED:
        return "execution_builder"
    else:
        return END

def build_graph():
    graph = StateGraph(SAATHIState)
    
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("life_event_predictor", predict_life_event)
    graph.add_node("product_recommender", recommend_products)
    graph.add_node("language_adapter", adapt_language)
    graph.add_node("execution_builder", build_execution_payload)
    
    graph.set_entry_point("supervisor")
    
    graph.add_conditional_edges("supervisor", route_after_supervisor)
    graph.add_edge("life_event_predictor", "supervisor")
    graph.add_edge("product_recommender", "supervisor")
    graph.add_edge("language_adapter", END)       # Sends message, waits for reply
    graph.add_edge("execution_builder", END)      # Sends consent payload, waits for OTP
    
    return graph.compile()

saathi_graph = build_graph()
