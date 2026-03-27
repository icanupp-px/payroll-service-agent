from functools import lru_cache
from langgraph.graph.state import END, START, StateGraph

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.payroll_status_lookup import (
    _select_payroll_status_branch,
    compose_result,
    fetch_holds,
    fetch_status_by_check_date,
    fetch_status_by_current_payroll,
    request_router,
)
from app.payroll_service_agent.nodes.validate_input import (
    extract_input_fields,
    validate_input_fields,
    validation_complete,
)


def create_input_validation_subgraph():
    workflow = StateGraph(PayrollServiceGraphState, output_schema=PayrollServiceGraphState)

    workflow.add_node("extract_input_fields", extract_input_fields)
    workflow.add_node("validate_input_fields", validate_input_fields)
    workflow.add_node("validation_complete", validation_complete)

    workflow.add_edge(START, "extract_input_fields")
    workflow.add_edge("extract_input_fields", "validate_input_fields")
    workflow.add_edge("validate_input_fields", "validation_complete")
    workflow.add_edge("validation_complete", END)

    return workflow.compile()


def create_payroll_status_lookup_subgraph():
    workflow = StateGraph(PayrollServiceGraphState, output_schema=PayrollServiceGraphState)

    workflow.add_node("fetch_status_by_check_date", fetch_status_by_check_date)
    workflow.add_node("fetch_status_by_current_payroll",
                      fetch_status_by_current_payroll)
    workflow.add_node("fetch_holds", fetch_holds)
    workflow.add_node("compose_result", compose_result)

    workflow.add_conditional_edges(
        START,
        _select_payroll_status_branch,
        {
            "fetch_status_by_check_date": "fetch_status_by_check_date",
            "fetch_status_by_current_payroll": "fetch_status_by_current_payroll",
        },
    )
    workflow.add_edge("fetch_status_by_check_date", "fetch_holds")
    workflow.add_edge("fetch_status_by_current_payroll", "fetch_holds")
    workflow.add_edge("fetch_holds", "compose_result")
    workflow.add_edge("compose_result", END)

    return workflow.compile()


def build_graph():
    workflow = StateGraph(PayrollServiceGraphState, output_schema=PayrollServiceGraphState)

    workflow.add_node("request_router", request_router)
    workflow.add_node("input_validation", create_input_validation_subgraph())
    workflow.add_node("payroll_status_lookup", create_payroll_status_lookup_subgraph())

    workflow.add_edge(START, "request_router")
    workflow.add_edge("request_router", "input_validation")
    workflow.add_edge("input_validation", "payroll_status_lookup")
    workflow.add_edge("payroll_status_lookup", END)

    return workflow.compile()
