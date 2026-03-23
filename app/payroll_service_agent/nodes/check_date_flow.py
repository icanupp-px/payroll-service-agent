import json
from urllib.error import HTTPError, URLError

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.payroll_status_lookup import (
    INVALID_CLIENT_ACCOUNT_MESSAGE,
    _is_allowed_status,
    fetch_payperiods_payload,
)
from app.payroll_service_agent.utils.logging_utils import setup_logger
from app.payroll_service_agent.utils.payroll_status_lookup_utils import PayrollStatusLookupUtils


log = setup_logger(__name__)


def fetch_status_by_check_date(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll statuses by check date")

    metadata = state.metadata or {}
    requested_check_date = metadata.get("asof") or metadata.get("checkDate")
    if not requested_check_date:
        log.error(
            "Missing required check date for payperiod list call. "
            "Set metadata.asof (or metadata.checkDate)."
        )
        state.status = "error"
        return state

    try:
        payload = fetch_payperiods_payload(
            metadata,
            requested_check_date=requested_check_date,
            prompt=state.prompt,
        )
        status_by_event_time = (
            PayrollStatusLookupUtils.extract_payperiod_status_map_by_event_time_and_check_date(
                payload, requested_check_date
            )
        )
        status_by_event_time = {
            k: v for k, v in status_by_event_time.items() if _is_allowed_status(v)
        }
        if status_by_event_time:
            state.payperiod_status_by_event_time = status_by_event_time
        else:
            # Some upstream responses do not include event time fields.
            # Fallback to an available status map so the caller still gets useful output.
            state.payperiod_status_by_event_time = (
                PayrollStatusLookupUtils.extract_payperiod_status_map_by_check_date(
                    payload, requested_check_date
                )
            )
            state.payperiod_status_by_event_time = {
                k: v
                for k, v in state.payperiod_status_by_event_time.items()
                if _is_allowed_status(v)
            }
        statuses = PayrollStatusLookupUtils.extract_payperiod_statuses_by_check_date(
            payload, requested_check_date
        )
        statuses = [status for status in statuses if _is_allowed_status(status)]
        state.status = ", ".join(statuses) if statuses else "unknown"
    except ValueError as e:
        log.error(f"Payperiod list API call skipped: {e}")
        if str(e) == INVALID_CLIENT_ACCOUNT_MESSAGE:
            state.status = INVALID_CLIENT_ACCOUNT_MESSAGE
            state.result = INVALID_CLIENT_ACCOUNT_MESSAGE
        else:
            state.status = "error"
    except HTTPError as e:
        response_body = ""
        try:
            raw_body = e.read()
            response_body = raw_body.decode("utf-8", errors="replace") if raw_body else ""
        except Exception:
            response_body = ""

        log.error(
            "Payperiod list API call failed: "
            f"HTTP {e.code}. Response body: {response_body}"
        )
        state.status = "error"
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        log.error(f"Payperiod list API call failed: {e}")
        state.status = "error"

    return state
