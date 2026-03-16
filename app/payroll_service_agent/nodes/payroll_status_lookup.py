import json
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.logging_utils import setup_logger


log = setup_logger(__name__)

ALL_PAYPERIOD_STATUSES = (
    "Entry,Initial,Completed,Completed by MEC,Processing,Reissued,Released,Reversed"
)


def _find_payperiod_status_value(data: object) -> str | None:
    if isinstance(data, dict):
        value = data.get("payPeriodStatusValue")
        if isinstance(value, str) and value.strip():
            return value
        for nested_value in data.values():
            found = _find_payperiod_status_value(nested_value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_payperiod_status_value(item)
            if found:
                return found
    return None


def _extract_payperiod_status_from_payload(payload: object, requested_payperiod_id: str) -> str | None:
    if not isinstance(payload, dict):
        return None

    content = payload.get("content")
    if not isinstance(content, dict):
        return None

    pay_periods = content.get("payPeriods")
    if not isinstance(pay_periods, list):
        return None

    # Prefer the matching payPeriodId when present.
    for item in pay_periods:
        if not isinstance(item, dict):
            continue
        if str(item.get("payPeriodId")) == requested_payperiod_id:
            value = item.get("payPeriodStatusValue")
            if isinstance(value, str) and value.strip():
                return value

    # Otherwise, return the first non-empty payPeriodStatusValue in the list.
    for item in pay_periods:
        if not isinstance(item, dict):
            continue
        value = item.get("payPeriodStatusValue")
        if isinstance(value, str) and value.strip():
            return value

    return None


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
            # payperiod_status must come from payPeriodStatusValue from the REST API response.
            payperiod_status_value = _extract_payperiod_status_from_payload(
                payload, state.payperiod_id
            ) or _find_payperiod_status_value(payload)
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

def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll holds")
    return state

def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Composing result")
    state.result = f"Hello, world! {state.request_id}"
    return state
