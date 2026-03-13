from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.models.payroll_status_lookup import PayrollStatus
from app.payroll_service_agent.utils.logging_utils import setup_logger


log = setup_logger(__name__)


def request_router(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Routing request")
    return state


def fetch_status(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll status")
    if state.payperiod_id:
        #TKTKTKTK Make the REST/LLM Call here
        pass
    else:
        pass

    return state

def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll holds")
    return state

def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Composing result")
    state.result = f"Hello, world! {state.request_id}"
    return state
