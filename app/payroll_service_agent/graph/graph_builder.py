from langgraph.graph.state import END, START, StateGraph

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.payroll_status_lookup import (
    compose_result,
    fetch_holds,
    fetch_status,
    request_router,
)



# An individual subgraph where we can furtherh elaborate use cases and workflows
def create_payroll_status_lookup_subgraph():
    workflow = StateGraph(PayrollServiceGraphState, output=PayrollServiceGraphState)

    workflow.add_node("fetch_status", fetch_status)
    workflow.add_node("fetch_holds", fetch_holds)

    workflow.add_edge(START, "fetch_status")
    workflow.add_edge("fetch_status", "fetch_holds")
    workflow.add_edge("fetch_holds", END)

    return workflow.compile()


def create_sample_subgraph():
    workflow = StateGraph(PayrollServiceGraphState, output=PayrollServiceGraphState)


    workflow.add_edge(START, END)

    return workflow.compile()

# Put together the "main" graph
def build_graph():
    workflow = StateGraph(PayrollServiceGraphState, output=PayrollServiceGraphState)

    workflow.add_node("request_router", request_router)
    workflow.add_node("payroll_status_lookup__", create_payroll_status_lookup_subgraph())
    workflow.add_node("sample_subgraph__", create_sample_subgraph())
    workflow.add_node("compose_result", compose_result)

    workflow.add_edge(START, "request_router")
    workflow.add_edge("request_router", "payroll_status_lookup__")
    workflow.add_edge("payroll_status_lookup__", "sample_subgraph__")
    workflow.add_edge("sample_subgraph__", "compose_result")
    workflow.add_edge("compose_result", END)

    return workflow.compile()
