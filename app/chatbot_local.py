import asyncio
import re
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

from app.api.models.input import ProcessRequest
from app.orchestrator import orchestrator
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
REPO_ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource(show_spinner=False)
def run_startup_test_suite() -> tuple[bool, str]:
    command = [
        "uv",
        "run",
        "--with",
        "pytest",
        "--with",
        "pytest-asyncio",
        "pytest",
        "tests",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "Failed to start test suite: 'uv' was not found on PATH."

    output = "\n".join(
        part.strip()
        for part in [completed.stdout, completed.stderr]
        if part and part.strip()
    )
    return completed.returncode == 0, output or "No test output was produced."


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
    effective_check_date = check_date or getattr(response, "resolved_check_date", None)
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
                f"{effective_check_date or 'unknown'} is <strong>\"{status}\"</strong> "
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
        "page": "0",
    }

    flow_type = "check_date"
    if is_current_payroll_prompt:
        metadata["checkdateasof"] = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        flow_type = "current_payroll"

    if flow_type != "current_payroll" and not check_date:
        return (
            "Please provide a check date, or ask for current payroll status.",
            False,
        )

    if flow_type == "check_date" and check_date:
        metadata["asof"] = check_date
        metadata["checkdateasof"] = check_date

    request = ProcessRequest(
        request_id=f"chat-{uuid.uuid4().hex[:8]}",
        prompt=prompt,
        check_date=check_date,
        flow_type=flow_type,
        metadata=metadata,
    )

    with st.spinner("Fetching payroll status..."):
        response = asyncio.run(orchestrator.orchestrate_payroll_service_processing(request))

    formatted_response = format_answer(response, check_date=check_date)
    return formatted_response, True


def main() -> None:
    st.set_page_config(page_title="Payroll Status Agent", page_icon="💬", layout="centered")
    with st.spinner("Running test suite before starting the chatbot..."):
        tests_passed, test_output = run_startup_test_suite()

    if not tests_passed:
        st.error("Startup test suite failed. Fix the failing tests before using the chatbot.")
        st.code(test_output)
        st.stop()
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
    st.title("Payroll Status Agent")
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
