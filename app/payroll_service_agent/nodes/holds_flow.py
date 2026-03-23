import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.logging_utils import setup_logger


log = setup_logger(__name__)


def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll holds")
    metadata = state.metadata or {}
    payperiod_id = getattr(state, "payperiod_id", None) or metadata.get("payperiod_id")
    if not payperiod_id:
        log.warning("No payperiod_id provided; skipping holds fetch.")
        return state

    if not settings.payroll_holds_api_base_url:
        log.warning("PAYROLL_HOLDS_API_BASE_URL not set; skipping REST call")
        state.holds = None
        return state

    holds_consumer = (
        metadata.get("x-payx-cnsmr")
        or metadata.get("x_payx_cnsmr")
        or metadata.get("consumer")
        or metadata.get("x-consumer")
        or metadata.get("source")
        or settings.payroll_holds_api_x_payx_cnsmr
        or settings.payroll_holds_api_consumer
    )
    if not holds_consumer:
        log.error(
            "Missing required x-payx-cnsmr value for payroll holds call. "
            "Set metadata.x-payx-cnsmr or PAYROLL_HOLDS_API_X_PAYX_CNSMR."
        )
        state.holds = None
        return state

    query = {
        "userguid": metadata.get("userguid"),
        "cltacctnbrs": metadata.get("cltacctnbrs"),
    }
    query = {k: v for k, v in query.items() if v is not None}
    url = (
        settings.payroll_holds_api_base_url.rstrip("/")
        + f"/{payperiod_id}?"
        + urlencode(query)
    )
    log.info(f"Payroll holds API URL: {url}")

    headers = {
        "Accept": "application/json",
        "x-payx-cnsmr": holds_consumer,
    }
    if settings.payroll_holds_api_key:
        headers["Authorization"] = f"Bearer {settings.payroll_holds_api_key}"

    log.info(f"Payroll holds API request headers: {headers}")

    req = Request(url, headers=headers, method="GET")

    ssl_ctx = None
    if settings.payroll_holds_api_ca_bundle_path:
        ssl_ctx = ssl.create_default_context(cafile=settings.payroll_holds_api_ca_bundle_path)
    elif not settings.payroll_holds_api_verify_ssl:
        ssl_ctx = ssl._create_unverified_context()  # dev-only

    try:
        log.info(f"Making payroll holds API request: url={url}, headers={headers}")
        with urlopen(req, timeout=settings.payroll_holds_api_timeout_s, context=ssl_ctx) as resp:
            log.info(
                f"Payroll holds API response object: status={getattr(resp, 'status', None)}, headers={dict(resp.headers)}"
            )
            resp_body = resp.read().decode("utf-8")
            log.info(f"Payroll holds API raw response: {resp_body}")
            data = json.loads(resp_body)

            holds = []
            content = data.get("content") if isinstance(data, dict) else None
            client_payroll_holds = (
                content.get("clientPayrollHolds")
                if content and isinstance(content, dict)
                else None
            )
            if client_payroll_holds and isinstance(client_payroll_holds, list):
                for hold in client_payroll_holds:
                    if not isinstance(hold, dict):
                        continue
                    filtered = {
                        "systemHoldType": hold.get("systemHoldType"),
                        "clientPayrollHoldId": hold.get("clientPayrollHoldId"),
                        "payPeriodId": hold.get("payPeriodId"),
                        "active": hold.get("active"),
                    }
                    holds.append(filtered)
            state.holds = holds if holds else None
            log.info(f"Fetched {len(state.holds) if state.holds else 0} holds.")
    except HTTPError as e:
        response_body = ""
        try:
            raw_body = e.read()
            response_body = raw_body.decode("utf-8", errors="replace") if raw_body else ""
        except Exception:
            response_body = ""
        log.error(
            f"Payroll holds API call failed: HTTP {e.code} for {url}. Response body: {response_body}"
        )
        state.holds = None
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        log.error(f"Payroll holds API call failed: {e}")
        state.holds = None

    return state
