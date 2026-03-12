from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.models.payroll_status_lookup import PayrollStatus


def request_router(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    return state


def fetch_status(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    if state.payperiod_id:
        #TKTKTKTK Make the REST Call here
        pass
    else:
        pass

    return state


def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    state.result = f"Hello, world! {state.request_id}"
    return state
