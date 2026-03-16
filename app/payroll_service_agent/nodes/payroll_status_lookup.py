import json
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.logging_utils import setup_logger


log = setup_logger(__name__)


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
    query = {
        "status": metadata.get("status", "Completed"),
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

    headers = {"Accept": "application/json"}
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
            # Best-effort extraction; depends on the API response shape
            state.status = (
                payload.get("status")
                or payload.get("payperiodStatus")
                or payload.get("payperiod", {}).get("status")
                or query.get("status")
                or "unknown"
            )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as e:
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
