import asyncio
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import streamlit as st
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.api.models.input import ProcessRequest
from app.orchestrator import orchestrator
from app.payroll_service_agent.nodes.payroll_status_lookup import fetch_payperiods_payload
from app.payroll_service_agent.nodes.payroll_status_lookup import INVALID_CLIENT_ACCOUNT_MESSAGE

CHECK_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
EXPLICIT_CHECK_DATE_PATTERN = re.compile(
    r"\bcheck\s*date\s*:?[\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})\b",
    re.IGNORECASE,
)
CURRENT_PAYROLL_PATTERN = re.compile(
    r"\b(current payroll|my current payroll|current pay ?period|latest payroll)\b",
    re.IGNORECASE,
)
PAYROLL_STATUS_INTENT_PATTERN = re.compile(
    r"\b(payroll|pay ?period|status|check date)\b",
    re.IGNORECASE,
)
ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY = (
    "Entry,Initial,Completed,Completed by MEC,Processing,Reissued,Released,Reversed,Time Delay"
)


class CurrentPayrollSelection(BaseModel):
    check_date: str | None = None
    submission_time: str | None = None
    status: str | None = None


def _fetch_payperiods_payload(metadata: dict[str, str], page: str, prompt: str | None = None) -> object:
    metadata_with_page = dict(metadata)
    metadata_with_page["page"] = page
    return fetch_payperiods_payload(metadata_with_page, prompt=prompt)


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
        if not isinstance(status, str) or not status.strip():
            continue
        candidates.append(
            {
                "checkDate": check_date,
                "payPeriodStatusValue": status,
                "payPeriodStatusEventTime": submission_time or "",
            }
        )
    return candidates


def _heuristic_current_selection(candidates: list[dict[str, str]]) -> CurrentPayrollSelection | None:
    if not candidates:
        return None

    now_utc = datetime.now(timezone.utc)

    def parse_timestamp(ts: str) -> datetime | None:
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

    def score(item: dict[str, str]) -> tuple[float, str, str]:
        event_time = parse_timestamp(item.get("payPeriodStatusEventTime", ""))
        if event_time is not None:
            delta_seconds = abs((event_time - now_utc).total_seconds())
            return (delta_seconds, item.get("payPeriodStatusEventTime", ""), item.get("checkDate", ""))
        # If event time is missing/unparseable, push to back and tie-break by latest checkDate.
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


def _resolve_current_payroll(prompt: str, metadata: dict[str, str], page: str) -> CurrentPayrollSelection | None:
    payload = _fetch_payperiods_payload(metadata, page, prompt=prompt)
    candidates = _extract_payperiod_candidates(payload)
    if not candidates:
        return None

    llm_selection = None
    try:
        llm_selection = _llm_current_selection(prompt, candidates)
    except Exception:
        llm_selection = None

    if llm_selection and llm_selection.status:
        submission_time = llm_selection.submission_time or llm_selection.check_date
        return CurrentPayrollSelection(
            check_date=llm_selection.check_date,
            submission_time=submission_time,
            status=llm_selection.status,
        )

    return _heuristic_current_selection(candidates)


def parse_prompt(prompt: str) -> tuple[str | None, bool]:
    prompt_text = prompt or ""

    explicit_check_date_match = EXPLICIT_CHECK_DATE_PATTERN.search(prompt_text)
    check_date_match = CHECK_DATE_PATTERN.search(prompt_text)
    check_date = None
    if explicit_check_date_match:
        check_date = explicit_check_date_match.group(1)
    elif check_date_match:
        check_date = check_date_match.group(0)

    has_check_date_phrase = bool(re.search(r"\bcheck\s*date\b", prompt_text, re.IGNORECASE))
    has_explicit_current_phrase = bool(CURRENT_PAYROLL_PATTERN.search(prompt or ""))
    has_payroll_intent = bool(PAYROLL_STATUS_INTENT_PATTERN.search(prompt or ""))
    is_current_payroll_prompt = bool(
        not check_date
        and not has_check_date_phrase
        and (has_explicit_current_phrase or has_payroll_intent)
    )

    return check_date, is_current_payroll_prompt


def format_answer(response, check_date: str | None = None) -> str:
    if response.payperiod_status:
        if response.payperiod_status == INVALID_CLIENT_ACCOUNT_MESSAGE:
            return INVALID_CLIENT_ACCOUNT_MESSAGE
        return f'Payperiod status: <strong>"{response.payperiod_status}"</strong>'

    if response.payroll_status_by_submit_time:
        lines = []
        for submit_time, status in response.payroll_status_by_submit_time.items():
            submission_date = submit_time.split("T", 1)[0].split(" ", 1)[0]
            lines.append(
                "Your payroll status for this Check date : "
                f"{check_date or 'unknown'} is <strong>\"{status}\"</strong> "
                f"for the submission time : {submission_date}"
            )
        return "\n".join(lines)

    return (
        "No payroll status was returned for the input. "
        "Please try again."
    )


def process_prompt(
    prompt: str,
) -> tuple[str, bool]:
    prompt = (prompt or "").strip()
    check_date, is_current_payroll_prompt = parse_prompt(prompt)

    if not prompt:
        return (
            "Please enter a prompt. For example: What is the status of my current payroll?",
            False,
        )

    metadata = {
        "userguid": "CA:12345",
        "projection": "payperiod",
        "x-payx-cnsmr": "CA DOMAIN",
    }
    page = "0"

    if is_current_payroll_prompt:
        metadata["checkdateasof"] = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        try:
            with st.spinner("Finding current payroll status..."):
                selection = _resolve_current_payroll(prompt, metadata, page)
        except ValueError as exc:
            if str(exc) == INVALID_CLIENT_ACCOUNT_MESSAGE:
                return INVALID_CLIENT_ACCOUNT_MESSAGE, False
            raise
        if not selection or not selection.status:
            return (
                "No payroll status was returned for the input. "
                "Please try again.",
                True,
            )
        check_date = selection.check_date or date.today().isoformat()
        submission_time = selection.submission_time or check_date
        status = selection.status
        formatted_response = (
            "Your payroll status for this Check date : "
            f"{check_date} is <strong>\"{status}\"</strong> "
            f"for the submission time : {submission_time.split('T', 1)[0].split(' ', 1)[0]}"
        )
        return formatted_response, True

    if not check_date:
        return (
            "Please provide a check date, or ask for current payroll status.",
            False,
        )

    if check_date:
        metadata["asof"] = check_date
        metadata["checkdateasof"] = check_date
        metadata["page"] = page

    request = ProcessRequest(
        request_id=f"chat-{uuid.uuid4().hex[:8]}",
        prompt=prompt,
        check_date=check_date,
        metadata=metadata,
    )

    with st.spinner("Fetching payroll status..."):
        response = asyncio.run(orchestrator.orchestrate_payroll_service_processing(request))

    formatted_response = format_answer(response, check_date=check_date)
    return formatted_response, True


def main() -> None:
    st.set_page_config(page_title="Payroll Status Chatbot", page_icon="💬", layout="centered")
    st.markdown(
        """
        <style>
        .chatbot-response {
            background: #ffffff;
            border: 1px solid #d9d9d9;
            border-radius: 10px;
            padding: 12px 14px;
            color: #111111;
            margin-top: 8px;
            white-space: pre-wrap;
            line-height: 1.5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Payroll Status Chatbot")
    st.caption(
        "Ask in plain text, for example: 'status for check date 2025-03-31', "
        "'status for 2025-03-31', or 'What's the status of my current payroll?'."
    )

    if "last_response" not in st.session_state:
        st.session_state.last_response = ""

    prompt = st.text_area("Prompt", placeholder="What is the status for check date 2025-03-31?")

    if st.button("Get status", type="primary"):
        try:
            formatted_response, _ = process_prompt(
                prompt=prompt,
            )
        except Exception as exc:
            st.error(str(exc))
            return

        st.session_state.last_response = formatted_response

    if st.session_state.last_response:
        st.markdown(
            f'<div class="chatbot-response">{st.session_state.last_response}</div>',
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
