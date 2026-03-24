import json
import os
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from pydantic import BaseModel


class CrossAppMappingSelection(BaseModel):
    ca_client_acct_nbr: str | None = None


class CurrentPayrollSelectionResult(BaseModel):
    check_date: str | None = None
    submission_time: str | None = None
    status: str | None = None


class LlmSelectionUtility:
    @staticmethod
    def extract_ca_client_account(
        ent_client_account: str,
        crossapp_payload: object,
    ) -> str | None:
        if not os.getenv("OPENAI_API_KEY"):
            return None

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
        if response and isinstance(response.ca_client_acct_nbr, str) and response.ca_client_acct_nbr.strip():
            return response.ca_client_acct_nbr
        return None

    @staticmethod
    def select_current_payroll(
        prompt: str,
        candidates: list[dict[str, str]],
    ) -> CurrentPayrollSelectionResult | None:
        if not candidates:
            return None
        if not os.getenv("OPENAI_API_KEY"):
            return None

        model_name = os.getenv("CHATBOT_CURRENT_PAYROLL_MODEL", "gpt-4o-mini")
        llm = ChatOpenAI(model=model_name, temperature=0)
        structured_llm = llm.with_structured_output(CurrentPayrollSelectionResult)

        candidates_for_model = candidates[:60]
        return structured_llm.invoke(
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
