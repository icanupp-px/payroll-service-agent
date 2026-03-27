import json
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.crossapp_mapping_utility import CrossAppMappingUtility
from app.payroll_service_agent.utils.logging_utils import setup_logger
from app.payroll_service_agent.utils.payroll_status_lookup_utils import (
    CurrentPayrollSelectionUtils,
    INVALID_CLIENT_ACCOUNT_MESSAGE,
    PayrollApiUtils,
    PayrollStatusLookupUtils,
)


log = setup_logger(__name__)


def request_router(state):
    log.info("Routing request")
    return state


def _select_payroll_status_branch(state: PayrollServiceGraphState) -> str:
    metadata = state.metadata or {}
    flow_type = (state.flow_type or metadata.get("flow_type") or "").strip().lower()
    has_check_date = bool(metadata.get("checkDate") or metadata.get("asof"))

    if flow_type == "current_payroll":
        return "fetch_status_by_current_payroll"
    if flow_type == "holds":
        # Route holds to check-date or current-payroll depending on whether a date was supplied
        return "fetch_status_by_check_date" if has_check_date else "fetch_status_by_current_payroll"
    if has_check_date:
        return "fetch_status_by_check_date"
    return "fetch_status_by_current_payroll"


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
        all_pay_periods = PayrollStatusLookupUtils.fetch_all_payperiods(
            metadata,
            requested_check_date=requested_check_date,
            prompt=state.prompt,
        )
        log.info(f"Aggregated payperiods list (all pages): {json.dumps(all_pay_periods, default=str)[:1000]}" if all_pay_periods else "No payperiods found.")
        # Aggregate status_by_event_time across all pages
        status_by_event_time = {}
        for item in all_pay_periods:
            if str(item.get("checkDate")) == requested_check_date:
                event_time = item.get("payPeriodStatusEventTime")
                status_value = item.get("payPeriodStatusValue")
                if event_time and status_value and PayrollStatusLookupUtils.is_allowed_status(status_value):
                    status_by_event_time[event_time] = status_value
        if status_by_event_time:
            state.payperiod_status_by_event_time = status_by_event_time
        else:
            # Fallback: aggregate by check date only
            status_by_id = {}
            for item in all_pay_periods:
                if str(item.get("checkDate")) == requested_check_date:
                    payperiod_id = item.get("payPeriodId")
                    status_value = item.get("payPeriodStatusValue")
                    if payperiod_id and status_value and PayrollStatusLookupUtils.is_allowed_status(status_value):
                        status_by_id[str(payperiod_id)] = status_value
            state.payperiod_status_by_event_time = status_by_id
        # Aggregate statuses for state.status
        statuses = [item.get("payPeriodStatusValue") for item in all_pay_periods if str(item.get("checkDate")) == requested_check_date and PayrollStatusLookupUtils.is_allowed_status(item.get("payPeriodStatusValue"))]
        state.status = ", ".join(statuses) if statuses else "unknown"

        # Holds flow: capture payperiod_id for qualifying payroll statuses
        if (state.flow_type or "").strip().lower() == "holds":
            _HOLDS_QUALIFYING_STATUSES = {"Released", "Processing"}
            payperiod_id = PayrollStatusLookupUtils.extract_payperiod_id_for_qualified_status(
                payload, requested_check_date, _HOLDS_QUALIFYING_STATUSES
            )
            if payperiod_id:
                state.payperiod_id = payperiod_id
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



def fetch_status_by_current_payroll(
    state: PayrollServiceGraphState,
) -> PayrollServiceGraphState:
    log.info("Fetching payroll status for current-payroll flow")

    metadata = state.metadata or {}
    try:
        all_pay_periods = PayrollStatusLookupUtils.fetch_all_payperiods(
            metadata,
            requested_check_date=None,
            prompt=state.prompt,
        )
        log.info(f"Aggregated payperiods list (all pages): {json.dumps(all_pay_periods, default=str)[:1000]}" if all_pay_periods else "No payperiods found.")
        candidates = CurrentPayrollSelectionUtils.extract_payperiod_candidates({"content": {"payPeriods": all_pay_periods}})
        if not candidates:
            state.status = "unknown"
            state.payperiod_status_by_event_time = None
            return state

        llm_selection = None
        try:
            llm_selection = CurrentPayrollSelectionUtils.llm_current_selection(
                state.prompt or "", candidates
            )
        except Exception:
            llm_selection = None

        selection = (
            llm_selection
            if llm_selection and llm_selection.status
            else CurrentPayrollSelectionUtils.heuristic_current_selection(candidates)
        )
        if not selection or not selection.status:
            state.status = "unknown"
            state.payperiod_status_by_event_time = None
            return state

        submission_time = selection.submission_time or selection.check_date or "current"
        state.payperiod_status_by_event_time = {submission_time: selection.status}
        state.status = selection.status

        # Holds flow: capture payperiod_id when status qualifies
        if (
            (state.flow_type or "").strip().lower() == "holds"
            and isinstance(selection.status, str)
            and selection.status.strip().upper() in {"RELEASED", "PROCESSING"}
        ):
            if selection.payperiod_id:
                state.payperiod_id = selection.payperiod_id

        if selection.check_date:
            metadata["asof"] = selection.check_date
            state.metadata = metadata
    except ValueError as e:
        log.error(f"Current-payroll API call skipped: {e}")
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
            "Current-payroll API call failed: "
            f"HTTP {e.code}. Response body: {response_body}"
        )
        state.status = "error"
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        log.error(f"Current-payroll API call failed: {e}")
        state.status = "error"

    return state


def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll holds")
    metadata = state.metadata or {}
    is_holds_flow = (state.flow_type or metadata.get("flow_type") or "").strip().lower() == "holds"
    payperiod_id = getattr(state, "payperiod_id", None) or metadata.get("payperiod_id")
    if not payperiod_id:
        if is_holds_flow:
            # For holds prompts, this usually means no qualifying status (Released/Processing)
            # was found for the selected payroll, so return an explicit no-holds result.
            log.info(
                "No qualifying payperiod_id found for holds flow; "
                "returning empty holds result without calling holds API."
            )
            state.holds = []
        else:
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

    resolved_client_account = metadata.get("cltacctnbrs")
    if not resolved_client_account:
        resolved_client_account, _ = CrossAppMappingUtility.resolve_ca_client_account_number(
            metadata,
            state.prompt,
        )
        if resolved_client_account:
            metadata["cltacctnbrs"] = resolved_client_account
            state.metadata = metadata
        else:
            log.error(
                "Missing required cltacctnbrs value for payroll holds call. "
                "Could not resolve CA client account from prompt/metadata."
            )
            state.holds = None
            return state

    query = {
        "userguid": metadata.get("userguid"),
        "cltacctnbrs": resolved_client_account,
    }
    query = {key: value for key, value in query.items() if value is not None}
    url = settings.payroll_holds_api_base_url.rstrip("/") + f"/{payperiod_id}?" + urlencode(query)
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
                "Payroll holds API response object: "
                f"status={getattr(resp, 'status', None)}, headers={dict(resp.headers)}"
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
            state.holds = holds
            log.info(f"Fetched {len(state.holds)} holds.")
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


def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Composing result")
    return state
