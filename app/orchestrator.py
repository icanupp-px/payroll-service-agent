from datetime import datetime, timezone
import asyncio

from app.api.models.input import ProcessRequest, ProcessResponse
from app.payroll_service_agent.graph.graph_builder import build_graph
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState


class PayrollServiceOrchestrator:

    def __init__(self) -> None:
        # Build once and reuse
        self.graph = build_graph()

    async def orchestrate_payroll_service_processing(self, request: ProcessRequest) -> ProcessResponse:
        started_at = datetime.now(timezone.utc)

        metadata = dict(request.metadata or {})
        if request.check_date:
            metadata.setdefault("asof", request.check_date)
        flow_type = (request.flow_type or metadata.get("flow_type") or "check_date").strip().lower()
        metadata.setdefault("flow_type", flow_type)

        initial_state = PayrollServiceGraphState(
            request_id=request.request_id,
            prompt=request.prompt,
            flow_type=flow_type,
            metadata=metadata,
            status=None,
            payperiod_status_by_event_time=None,
            result=None,
        )

        graph_output = await asyncio.to_thread(self.graph.invoke, initial_state)
        final_state = (
            PayrollServiceGraphState(**graph_output)
            if isinstance(graph_output, dict)
            else graph_output
        )

        _ = datetime.now(timezone.utc) - started_at

        # Extract holds for top-level field, similar to payperiod_status
        payperiod_holds = None
        if hasattr(final_state, "holds"):
            payperiod_holds = final_state.holds
        payperiod_status = None
        payroll_status_by_submit_time = None
        payroll_status_by_submit_time = final_state.payperiod_status_by_event_time
        if not payroll_status_by_submit_time and final_state.status:
            payperiod_status = final_state.status

        return ProcessResponse(
            request_id=request.request_id,
            payperiod_status=payperiod_status,
            resolved_check_date=(final_state.metadata or {}).get("asof"),
            payroll_status_by_submit_time=payroll_status_by_submit_time,
            payperiod_holds=payperiod_holds,
        )


# Singleton instance
orchestrator = PayrollServiceOrchestrator()
