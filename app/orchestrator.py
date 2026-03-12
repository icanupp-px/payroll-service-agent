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
            status=None,
            result=None,
        )

        graph_output = await asyncio.to_thread(self.graph.invoke, initial_state)
        final_state = (
            PayrollServiceGraphState(**graph_output)
            if isinstance(graph_output, dict)
            else graph_output
        )

        _ = datetime.now(timezone.utc) - started_at

        return ProcessResponse(
            request_id=request.request_id,
            status="completed",
            result=final_state.result or "No result generated.",
        )


# Singleton instance
orchestrator = PayrollServiceOrchestrator()
