from functools import lru_cache

from langgraph.graph.state import END, START, StateGraph

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.payroll_status_lookup import (
    compose_result,
    fetch_holds,
    fetch_status_by_check_date,
    request_router,
)


def _select_status_node(state: PayrollServiceGraphState) -> str:
    metadata = state.metadata or {}
    has_check_date = bool(metadata.get("checkDate") or metadata.get("asof"))

    if has_check_date:
        return "fetch_status_by_check_date"
    # Default to check-date flow; request validation is expected to provide asof/checkDate.
    return "fetch_status_by_check_date"


@lru_cache(maxsize=1)
def build_graph():
    workflow = StateGraph(PayrollServiceGraphState, output=PayrollServiceGraphState)

    workflow.add_node("request_router", request_router)
    workflow.add_node("fetch_status_by_check_date", fetch_status_by_check_date)
    workflow.add_node("compose_result", compose_result)
    workflow.add_node("fetch_holds", fetch_holds)

    workflow.add_edge(START, "request_router")
    workflow.add_conditional_edges(
        "request_router",
        _select_status_node,
        {
            "fetch_status_by_check_date": "fetch_status_by_check_date",
        },
    )
    workflow.add_edge("fetch_status_by_check_date", "fetch_holds")
    workflow.add_edge("fetch_holds", "compose_result")
    workflow.add_edge("compose_result", END)

    return workflow.compile()
