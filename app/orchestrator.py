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

        initial_state = PayrollServiceGraphState(
            request_id=request.request_id,
            payperiod_id=request.payperiod_id,
            metadata=request.metadata,
            status=None,
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
        return ProcessResponse(
            request_id=request.request_id,
            status="completed",
            payperiod_status=final_state.status,
            payperiod_holds=payperiod_holds,
        )


# Singleton instance
orchestrator = PayrollServiceOrchestrator()
