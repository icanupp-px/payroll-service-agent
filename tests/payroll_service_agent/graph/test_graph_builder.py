from app.payroll_service_agent.graph.graph_builder import (
    build_graph,
    create_payroll_status_lookup_subgraph,
)
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.graph import graph_builder


def test_payroll_status_lookup_subgraph_routes_check_date(monkeypatch) -> None:
    def fetch_by_check_date(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
        metadata = dict(state.metadata or {})
        metadata["path"] = "check-date"
        state.metadata = metadata
        state.status = "Completed"
        return state

    def fetch_current(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
        metadata = dict(state.metadata or {})
        metadata["path"] = "current-payroll"
        state.metadata = metadata
        return state

    def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
        metadata = dict(state.metadata or {})
        metadata["holds_ran"] = "yes"
        state.metadata = metadata
        return state

    monkeypatch.setattr(graph_builder, "fetch_status_by_check_date", fetch_by_check_date)
    monkeypatch.setattr(graph_builder, "fetch_status_by_current_payroll", fetch_current)
    monkeypatch.setattr(graph_builder, "fetch_holds", fetch_holds)
    monkeypatch.setattr(graph_builder, "compose_result", lambda state: state)
    graph_builder.create_payroll_status_lookup_subgraph.cache_clear()

    graph = create_payroll_status_lookup_subgraph()
    result = graph.invoke(
        PayrollServiceGraphState(
            request_id="req-graph-1",
            metadata={"asof": "2025-03-31"},
        )
    )

    assert result["metadata"]["path"] == "check-date"
    assert result["metadata"]["holds_ran"] == "yes"


def test_build_graph_routes_through_request_router_and_subgraph(monkeypatch) -> None:
    def request_router(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
        metadata = dict(state.metadata or {})
        metadata["router_ran"] = "yes"
        state.metadata = metadata
        return state

    def fetch_current(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
        metadata = dict(state.metadata or {})
        metadata["path"] = "current-payroll"
        state.metadata = metadata
        state.status = "Processing"
        return state

    monkeypatch.setattr(graph_builder, "request_router", request_router)
    monkeypatch.setattr(graph_builder, "fetch_status_by_check_date", lambda state: state)
    monkeypatch.setattr(graph_builder, "fetch_status_by_current_payroll", fetch_current)
    monkeypatch.setattr(graph_builder, "fetch_holds", lambda state: state)
    monkeypatch.setattr(graph_builder, "compose_result", lambda state: state)
    graph_builder.create_payroll_status_lookup_subgraph.cache_clear()
    graph_builder.build_graph.cache_clear()

    graph = build_graph()
    result = graph.invoke(
        PayrollServiceGraphState(
            request_id="req-graph-2",
            flow_type="current_payroll",
            metadata={"flow_type": "current_payroll"},
        )
    )

    assert result["metadata"]["router_ran"] == "yes"
    assert result["metadata"]["path"] == "current-payroll"
    assert result["status"] == "Processing"