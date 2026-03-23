import json
import os
import re
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.logging_utils import setup_logger
from app.payroll_service_agent.utils.payroll_status_lookup_utils import PayrollStatusLookupUtils


log = setup_logger(__name__)

ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY = (
    "Completed,Completed by MEC,Processing,Reissued,Released,Reversed,Time Delay"
)
OMITTED_STATUSES = {"ENTRY", "INITIAL"}
ENT_ID_PATTERN = re.compile(r"\bENT:\s*[A-Za-z0-9]+\b", re.IGNORECASE)
CA_CLIENT_ACCOUNT_PATTERN = re.compile(r"^(?:CA:)?[A-Za-z0-9]+$", re.IGNORECASE)
INVALID_CLIENT_ACCOUNT_MESSAGE = "Please send a valid Client Account number"
DEFAULT_USERGUID = "CA:12345"
FALLBACK_USERGUID = "CA:751234564482"
DEFAULT_PROJECTION = "payperiod"
DEFAULT_PAGE = "0"
DEFAULT_X_PAYX_CNSMR = "CA DOMAIN"


class CrossAppMappingSelection(BaseModel):
    ca_client_acct_nbr: str | None = None


def _resolve_payx_consumer(effective_metadata: dict[str, str]) -> str | None:
    return (
        effective_metadata.get("x-payx-cnsmr")
        or effective_metadata.get("x_payx_cnsmr")
        or effective_metadata.get("consumer")
        or effective_metadata.get("x-consumer")
        or effective_metadata.get("source")
        or DEFAULT_X_PAYX_CNSMR
        or settings.payroll_status_api_x_payx_cnsmr
        or settings.payroll_status_api_consumer
    )


def _crossapp_ssl_context() -> ssl.SSLContext | None:
    if settings.crossapp_mappings_api_ca_bundle_path:
        return ssl.create_default_context(cafile=settings.crossapp_mappings_api_ca_bundle_path)
    if not settings.crossapp_mappings_api_verify_ssl:
        return ssl._create_unverified_context()  # dev-only
    return None


def _fetch_crossapp_mapping_payload(
    userguid: str,
    ent_client_account: str,
    payx_consumer: str,
) -> object:
    if not settings.crossapp_mappings_api_url:
        raise ValueError(INVALID_CLIENT_ACCOUNT_MESSAGE)

    url = settings.crossapp_mappings_api_url.rstrip("/") + "?" + urlencode(
        {
            "userguid": userguid,
            "cltacctnbrs": ent_client_account,
        }
    )

    headers = {
        "Accept": "application/json",
        "x-payx-cnsmr": payx_consumer,
    }
    req = Request(url, headers=headers, method="GET")
    with urlopen(
        req,
        timeout=settings.crossapp_mappings_api_timeout_s,
        context=_crossapp_ssl_context(),
    ) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_first_ca_client_account(payload: object) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("caClientAcctNbr")
        if isinstance(value, str) and value.strip():
            return value.strip()
        for nested in payload.values():
            found = _extract_first_ca_client_account(nested)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _extract_first_ca_client_account(item)
            if found:
                return found
    return None


def _extract_ca_client_account_via_llm(
    ent_client_account: str,
    crossapp_payload: object,
) -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return _extract_first_ca_client_account(crossapp_payload)

    model_name = os.getenv("CHATBOT_CURRENT_PAYROLL_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0)
    structured_llm = llm.with_structured_output(CrossAppMappingSelection)
    response = structured_llm.invoke(
        [
            (
                "system",
                "You extract a valid CA client account number from a cross-app mappings API response. "
                "Return only ca_client_acct_nbr in format CA:<alphanumeric>. "
                "If there is no valid value, return null.",
            ),
            (
                "human",
                "ENT client account from prompt: "
                f"{ent_client_account}\n\n"
                "Cross-app mappings payload JSON:\n"
                f"{json.dumps(crossapp_payload)}",
            ),
        ]
    )
    return response.ca_client_acct_nbr if response else None


def _normalize_ca_client_account(value: str) -> str | None:
    raw = (value or "").strip().upper()
    if not raw:
        return None
    if not CA_CLIENT_ACCOUNT_PATTERN.match(raw):
        return None
    if raw.startswith("CA:"):
        return raw
    return f"CA:{raw}"


def _resolve_ca_client_account_number(
    metadata: dict[str, str] | None,
    prompt: str | None,
) -> tuple[str | None, str | None]:
    effective_metadata = metadata or {}
    prompt_text = prompt or ""
    prompt_ent_match = ENT_ID_PATTERN.search(prompt_text)
    if prompt_text and not prompt_ent_match:
        return None, INVALID_CLIENT_ACCOUNT_MESSAGE

    ent_match = prompt_ent_match
    if not ent_match:
        return None, INVALID_CLIENT_ACCOUNT_MESSAGE

    userguid = effective_metadata.get("userguid") or DEFAULT_USERGUID
    if not userguid:
        return None, INVALID_CLIENT_ACCOUNT_MESSAGE

    payx_consumer = _resolve_payx_consumer(effective_metadata)
    if not payx_consumer:
        return None, INVALID_CLIENT_ACCOUNT_MESSAGE

    ent_client_account = re.sub(r"\s+", "", ent_match.group(0).upper())
    attempted_userguids: list[str] = []
    for candidate_userguid in [userguid, FALLBACK_USERGUID]:
        if not candidate_userguid or candidate_userguid in attempted_userguids:
            continue
        attempted_userguids.append(candidate_userguid)
        try:
            crossapp_payload = _fetch_crossapp_mapping_payload(
                userguid=candidate_userguid,
                ent_client_account=ent_client_account,
                payx_consumer=payx_consumer,
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
            continue

        ca_client_acct_nbr = _extract_ca_client_account_via_llm(
            ent_client_account,
            crossapp_payload,
        )
        if not isinstance(ca_client_acct_nbr, str):
            continue

        normalized = _normalize_ca_client_account(ca_client_acct_nbr)
        if not normalized:
            continue

        return normalized, None

    return None, INVALID_CLIENT_ACCOUNT_MESSAGE



def request_router(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Routing request")
    return state


def _default_current_checkdate_asof() -> str:
    # Current-payroll flow asks for the recent period anchored at UTC today minus 30 days.
    return (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()


def _is_allowed_status(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().upper() not in OMITTED_STATUSES


def fetch_payperiods_payload(
    metadata: dict[str, str] | None,
    requested_check_date: str | None = None,
    prompt: str | None = None,
) -> object:
    if not settings.payroll_status_api_base_url:
        raise ValueError("PAYROLL_STATUS_API_BASE_URL not set")

    effective_metadata = metadata or {}
    payx_consumer = _resolve_payx_consumer(effective_metadata)
    if not payx_consumer:
        raise ValueError(
            "Missing required x-payx-cnsmr value. "
            "Set metadata.x-payx-cnsmr or PAYROLL_STATUS_API_X_PAYX_CNSMR."
        )

    resolved_client_account, resolution_error = _resolve_ca_client_account_number(
        effective_metadata,
        prompt,
    )
    if resolution_error or not resolved_client_account:
        raise ValueError(INVALID_CLIENT_ACCOUNT_MESSAGE)

    query = {
        "status": ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY,
        "projection": DEFAULT_PROJECTION,
        "userguid": DEFAULT_USERGUID,
        "cltacctnbrs": resolved_client_account,
        "page": DEFAULT_PAGE,
    }
    if requested_check_date:
        query["asof"] = requested_check_date
        query["checkdateasof"] = requested_check_date
    else:
        query["checkdateasof"] = (
            effective_metadata.get("checkdateasof") or _default_current_checkdate_asof()
        )
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
        ssl_ctx = ssl.create_default_context(
            cafile=settings.payroll_status_api_ca_bundle_path)
    elif not settings.payroll_status_api_verify_ssl:
        ssl_ctx = ssl._create_unverified_context()  # dev-only

    with urlopen(req, timeout=settings.payroll_status_api_timeout_s, context=ssl_ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
            response_body = raw_body.decode(
                "utf-8", errors="replace") if raw_body else ""
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


def fetch_status(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    # Backward compatibility for any stale import paths expecting fetch_status.
    return fetch_status_by_check_date(state)


def fetch_holds(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll holds")
    if not state.payperiod_id:
        log.warning("No payperiod_id provided; skipping holds fetch.")
        return state

    if not settings.payroll_holds_api_base_url:
        log.warning("PAYROLL_HOLDS_API_BASE_URL not set; skipping REST call")
        state.holds = None
        return state

    metadata = state.metadata or {}
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

    # If consumer is present, proceed with API call as in fetch_status

    query = {
        "userguid": metadata.get("userguid"),
        "cltacctnbrs": metadata.get("cltacctnbrs"),
    }
    query = {k: v for k, v in query.items() if v is not None}
    url = (
        settings.payroll_holds_api_base_url.rstrip("/")
        + f"/{state.payperiod_id}?"
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
    if hasattr(settings, "payroll_holds_api_ca_bundle_path") and getattr(settings, "payroll_holds_api_ca_bundle_path", None):
        ssl_ctx = ssl.create_default_context(
            cafile=settings.payroll_holds_api_ca_bundle_path)
    elif not getattr(settings, "payroll_holds_api_verify_ssl", True):
        ssl_ctx = ssl._create_unverified_context()

    try:
        log.info(f"Making payroll holds API request: url={url}, headers={headers}")
        with urlopen(req, timeout=settings.payroll_holds_api_timeout_s, context=ssl_ctx) as resp:
            log.info(
                f"Payroll holds API response object: status={getattr(resp, 'status', None)}, headers={dict(resp.headers)}")
            resp_body = resp.read().decode("utf-8")
            log.info(f"Payroll holds API raw response: {resp_body}")
            data = json.loads(resp_body)
            # Extract only the relevant fields from the holds API response
            holds = []
            content = data.get("content") if isinstance(data, dict) else None
            client_payroll_holds = content.get(
                "clientPayrollHolds") if content and isinstance(content, dict) else None
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
            log.info(
                f"Fetched {len(state.holds) if state.holds else 0} holds.")
    except HTTPError as e:
        response_body = ""
        try:
            raw_body = e.read()
            response_body = raw_body.decode(
                "utf-8", errors="replace") if raw_body else ""
        except Exception:
            response_body = ""
        log.error(
            f"Payroll holds API call failed: HTTP {e.code} for {url}. Response body: {response_body}")
        state.holds = None
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        log.error(f"Payroll holds API call failed: {e}")
        state.holds = None
    return state


def compose_result(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Composing result")
    if not state.result:
        state.result = f"Hello, world! {state.request_id}"
    # No longer set state.result
    return state
