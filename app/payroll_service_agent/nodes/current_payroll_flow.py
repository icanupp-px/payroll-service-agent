import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes.payroll_status_lookup import (
    INVALID_CLIENT_ACCOUNT_MESSAGE,
    _is_allowed_status,
    fetch_payperiods_payload,
)
from app.payroll_service_agent.utils.logging_utils import setup_logger


log = setup_logger(__name__)


class CurrentPayrollSelection(BaseModel):
    check_date: str | None = None
    submission_time: str | None = None
    status: str | None = None


def _extract_payperiod_candidates(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        return []
    content = payload.get("content")
    if not isinstance(content, dict):
        return []
    pay_periods = content.get("payPeriods")
    if not isinstance(pay_periods, list):
        return []

    candidates: list[dict[str, str]] = []
    for item in pay_periods:
        if not isinstance(item, dict):
            continue
        check_date = item.get("checkDate")
        status = item.get("payPeriodStatusValue")
        submission_time = item.get("payPeriodStatusEventTime")
        if not isinstance(check_date, str) or not check_date.strip():
            continue
        if not isinstance(status, str) or not status.strip() or not _is_allowed_status(status):
            continue
        candidates.append(
            {
                "checkDate": check_date,
                "payPeriodStatusValue": status,
                "payPeriodStatusEventTime": submission_time or "",
            }
        )
    return candidates


def _parse_timestamp(ts: str) -> datetime | None:
    if not ts:
        return None
    normalized = ts.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _heuristic_current_selection(candidates: list[dict[str, str]]) -> CurrentPayrollSelection | None:
    if not candidates:
        return None

    now_utc = datetime.now(timezone.utc)

    def score(item: dict[str, str]) -> tuple[float, str, str]:
        event_time = _parse_timestamp(item.get("payPeriodStatusEventTime", ""))
        if event_time is not None:
            delta_seconds = abs((event_time - now_utc).total_seconds())
            return (delta_seconds, item.get("payPeriodStatusEventTime", ""), item.get("checkDate", ""))
        return (float("inf"), "", item.get("checkDate", ""))

    closest = sorted(candidates, key=score)
    item = closest[0]
    return CurrentPayrollSelection(
        check_date=item.get("checkDate"),
        submission_time=item.get("payPeriodStatusEventTime") or item.get("checkDate"),
        status=item.get("payPeriodStatusValue"),
    )


def _llm_current_selection(prompt: str, candidates: list[dict[str, str]]) -> CurrentPayrollSelection | None:
    if not candidates:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None

    model_name = os.getenv("CHATBOT_CURRENT_PAYROLL_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0)
    structured_llm = llm.with_structured_output(CurrentPayrollSelection)

    candidates_for_model = candidates[:60]
    response = structured_llm.invoke(
        [
            (
                "system",
                "You select the current payroll record from payperiod data. "
                "Primary rule: choose the record whose payPeriodStatusEventTime is closest to today's UTC date/time. "
                "If event times are missing, choose by closest checkDate to today.",
            ),
            (
                "human",
                "Prompt:\n"
                f"{prompt}\n\n"
                f"Today's UTC timestamp: {datetime.now(timezone.utc).isoformat()}\n\n"
                "Payperiod candidates JSON:\n"
                f"{json.dumps(candidates_for_model)}\n\n"
                "Return check_date from checkDate, submission_time from payPeriodStatusEventTime, "
                "and status from payPeriodStatusValue.",
            ),
        ]
    )
    return response


def fetch_status_by_current_payroll(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Fetching payroll status for current-payroll flow")

    metadata = state.metadata or {}
    try:
        payload = fetch_payperiods_payload(
            metadata,
            requested_check_date=None,
            prompt=state.prompt,
        )
        candidates = _extract_payperiod_candidates(payload)
        if not candidates:
            state.status = "unknown"
            state.payperiod_status_by_event_time = None
            return state

        llm_selection = None
        try:
            llm_selection = _llm_current_selection(state.prompt or "", candidates)
        except Exception:
            llm_selection = None

        selection = llm_selection if llm_selection and llm_selection.status else _heuristic_current_selection(candidates)
        if not selection or not selection.status:
            state.status = "unknown"
            state.payperiod_status_by_event_time = None
            return state

        submission_time = selection.submission_time or selection.check_date or "current"
        state.payperiod_status_by_event_time = {submission_time: selection.status}
        state.status = selection.status

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
