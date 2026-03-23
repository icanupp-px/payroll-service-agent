from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.logging_utils import setup_logger


log = setup_logger(__name__)


def request_router(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Routing request")
    return state


def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Composing result")
    return state
