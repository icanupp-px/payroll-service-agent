import json
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.utils.payroll_status_lookup import (
    extract_payperiod_status_from_payload,
    find_payperiod_status_value,
)
from app.payroll_service_agent.utils.logging_utils import setup_logger
from app.payroll_service_agent.utils.payroll_status_lookup_utils import PayrollStatusLookupUtils


log = setup_logger(__name__)

ALL_PAYPERIOD_STATUSES = (
    "Entry,Initial,Completed,Completed by MEC,Processing,Reissued,Released,Reversed"
)
ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY = (
    "Entry,Initial,Completed,Completed by MEC,Processing,Reissued,Released,Reversed,Time Delay"
)



def request_router(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Routing request")
    return state


def fetch_status(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll status")

    if not state.payperiod_id:
        state.status = "missing_payperiod_id"
        return state

    if not settings.payroll_status_api_base_url:
        log.warning("PAYROLL_STATUS_API_BASE_URL not set; skipping REST call")
        state.status = "skipped"
        return state

    # Expected query params (example): status=Completed&projection=payperiod&userguid=...&cltacctnbrs=...
    metadata = state.metadata or {}
    payx_consumer = (
        metadata.get("x-payx-cnsmr")
        or metadata.get("x_payx_cnsmr")
        or metadata.get("consumer")
        or metadata.get("x-consumer")
        or metadata.get("source")
        or settings.payroll_status_api_x_payx_cnsmr
        or settings.payroll_status_api_consumer
    )
    if not payx_consumer:
        log.error(
            "Missing required x-payx-cnsmr value for payperiod status call. "
            "Set metadata.x-payx-cnsmr or PAYROLL_STATUS_API_X_PAYX_CNSMR."
        )
        state.status = "error"
        return state

    query = {
        "status": ALL_PAYPERIOD_STATUSES,
        "projection": metadata.get("projection", "payperiod"),
        "userguid": metadata.get("userguid"),
        "cltacctnbrs": metadata.get("cltacctnbrs"),
    }
    # Drop missing required fields rather than sending "None"
    query = {k: v for k, v in query.items() if v is not None}

    url = (
        settings.payroll_status_api_base_url.rstrip("/")
        + f"/payperiods/{state.payperiod_id}?"
        + urlencode(query)
    )

    headers = {
        "Accept": "application/json",
        "x-payx-cnsmr": payx_consumer,
    }
    if settings.payroll_status_api_key:
        headers["Authorization"] = f"Bearer {settings.payroll_status_api_key}"

    req = Request(url, headers=headers, method="GET")

    ssl_ctx = None
    if settings.payroll_status_api_ca_bundle_path:
        ssl_ctx = ssl.create_default_context(cafile=settings.payroll_status_api_ca_bundle_path)
    elif not settings.payroll_status_api_verify_ssl:
        ssl_ctx = ssl._create_unverified_context()  # dev-only

    try:
        with urlopen(req, timeout=settings.payroll_status_api_timeout_s, context=ssl_ctx) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            requested_check_date = metadata.get("asof") or metadata.get("checkDate")
            if requested_check_date:
                actual_check_date = PayrollStatusLookupUtils.extract_check_date_for_payperiod_id(
                    payload, state.payperiod_id
                )
                if actual_check_date and actual_check_date != requested_check_date:
                    state.status = "check_date_mismatch"
                    state.result = (
                        "Provided check date does not match the requested payperiod id"
                    )
                    return state

            # payperiod_status must come from payPeriodStatusValue from the REST API response.
            payperiod_status_value = PayrollStatusLookupUtils.extract_payperiod_status_from_payload(
                payload, state.payperiod_id
            ) or PayrollStatusLookupUtils.find_payperiod_status_value(payload)
            state.status = payperiod_status_value or "unknown"
    except HTTPError as e:
        # Include upstream error payload so 4xx/5xx failures are actionable.
        response_body = ""
        try:
            raw_body = e.read()
            response_body = raw_body.decode("utf-8", errors="replace") if raw_body else ""
        except Exception:
            response_body = ""

        log.error(
            "Payperiod status API call failed: "
            f"HTTP {e.code} for {url}. Response body: {response_body}"
        )
        state.status = "error"
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        log.error(f"Payperiod status API call failed: {e}")
        state.status = "error"

    return state


def fetch_status_by_check_date(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll statuses by check date")

    if not settings.payroll_status_api_base_url:
        log.warning("PAYROLL_STATUS_API_BASE_URL not set; skipping REST call")
        state.status = "skipped"
        return state

    metadata = state.metadata or {}
    requested_check_date = metadata.get("asof") or metadata.get("checkDate")
    if not requested_check_date:
        log.error(
            "Missing required check date for payperiod list call. "
            "Set metadata.asof (or metadata.checkDate)."
        )
        state.status = "error"
        return state

    payx_consumer = (
        metadata.get("x-payx-cnsmr")
        or metadata.get("x_payx_cnsmr")
        or metadata.get("consumer")
        or metadata.get("x-consumer")
        or metadata.get("source")
        or settings.payroll_status_api_x_payx_cnsmr
        or settings.payroll_status_api_consumer
    )
    if not payx_consumer:
        log.error(
            "Missing required x-payx-cnsmr value for payperiod list call. "
            "Set metadata.x-payx-cnsmr or PAYROLL_STATUS_API_X_PAYX_CNSMR."
        )
        state.status = "error"
        return state

    query = {
        "status": ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY,
        "projection": metadata.get("projection", "payperiod"),
        "userguid": metadata.get("userguid"),
        "cltacctnbrs": metadata.get("cltacctnbrs"),
        "asof": requested_check_date,
        "page": metadata.get("page", "1"),
    }
    query = {k: v for k, v in query.items() if v is not None}

    url = settings.payroll_status_api_base_url.rstrip("/") + "/payperiods?" + urlencode(query)

    headers = {
        "Accept": "application/json",
        "x-payx-cnsmr": payx_consumer,
    }
    if settings.payroll_status_api_key:
        headers["Authorization"] = f"Bearer {settings.payroll_status_api_key}"

    req = Request(url, headers=headers, method="GET")

    ssl_ctx = None
    if settings.payroll_status_api_ca_bundle_path:
        ssl_ctx = ssl.create_default_context(cafile=settings.payroll_status_api_ca_bundle_path)
    elif not settings.payroll_status_api_verify_ssl:
        ssl_ctx = ssl._create_unverified_context()  # dev-only

    try:
        with urlopen(req, timeout=settings.payroll_status_api_timeout_s, context=ssl_ctx) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            status_by_event_time = (
                PayrollStatusLookupUtils.extract_payperiod_status_map_by_event_time_and_check_date(
                    payload, requested_check_date
                )
            )
            if status_by_event_time:
                state.payperiod_status_by_event_time = status_by_event_time
            statuses = PayrollStatusLookupUtils.extract_payperiod_statuses_by_check_date(
                payload, requested_check_date
            )
            state.status = ", ".join(statuses) if statuses else "unknown"
    except HTTPError as e:
        response_body = ""
        try:
            raw_body = e.read()
            response_body = raw_body.decode("utf-8", errors="replace") if raw_body else ""
        except Exception:
            response_body = ""

        log.error(
            "Payperiod list API call failed: "
            f"HTTP {e.code} for {url}. Response body: {response_body}"
        )
        state.status = "error"
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        log.error(f"Payperiod list API call failed: {e}")
        state.status = "error"

    return state

def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll holds")
    return state

def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Composing result")
    if not state.result:
        state.result = f"Hello, world! {state.request_id}"
    return state
