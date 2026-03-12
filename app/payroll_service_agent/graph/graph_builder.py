from functools import lru_cache

from langgraph.graph.state import END, START, StateGraph

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.payroll_status_lookup import (
    compose_result,
    fetch_status,
    request_router,
)


@lru_cache(maxsize=1)
def build_graph():
    workflow = StateGraph(PayrollServiceGraphState, output=PayrollServiceGraphState)

    workflow.add_node("request_router", request_router)
    workflow.add_node("fetch_status", fetch_status)
    workflow.add_node("compose_result", compose_result)

    workflow.add_edge(START, "request_router")
    workflow.add_edge("request_router", "fetch_status")
    workflow.add_edge("fetch_status", "compose_result")
    workflow.add_edge("compose_result", END)

    return workflow.compile()
