from graph.state import SAATHIState

async def supervisor_node(state: SAATHIState) -> SAATHIState:
    """
    Supervisor Node Stub.
    Responsible for classifying incoming events and routing to specialist agents.
    """
    # For now, just return state to pass through the workflow
    return state
