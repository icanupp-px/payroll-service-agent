import re

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.utils.crossapp_mapping_utility import (
    CrossAppMappingUtility,
    INVALID_CLIENT_ACCOUNT_MESSAGE,
)
from app.payroll_service_agent.utils.prompt import load_prompt
from app.payroll_service_agent.utils.logging_utils import setup_logger
from app.payroll_service_agent.utils.llm_selection_utility import LlmSelectionUtility


log = setup_logger(__name__)
PROMPTS = load_prompt("validate_input")

CHECK_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CURRENT_PAYROLL_PATTERN = re.compile(
    r"\b(current payroll|my current payroll|current pay ?period|latest payroll|current status)\b",
    re.IGNORECASE,
)
PAYROLL_STATUS_INTENT_PATTERN = re.compile(
    r"\b(payroll|pay ?period|status|check date)\b",
    re.IGNORECASE,
)
ENT_CLIENT_PATTERN = re.compile(r"\bENT:\s*[A-Za-z0-9-]+\b", re.IGNORECASE)
CLIENT_ID_LABEL_PATTERN = re.compile(
    r"\b(?:client\s*(?:id|account)|account)\s*:?\s*([A-Za-z0-9-]+)\b",
    re.IGNORECASE,
)
PAYPERIOD_ID_PATTERN = re.compile(
    r"\b(?:pay\s*period\s*id|payperiod\s*id|ppid)\s*:?\s*([A-Za-z0-9-]+)\b",
    re.IGNORECASE,
)
VALID_CHECK_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")



def extract_input_fields(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    # Pull client number, payperiod ID or check date off the message.
    # Can fetch prompts like this:
    # prompt = PROMPTS["extract_client_information"]
    return state


def validate_input_fields(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Validating extracted payroll request fields")

    ## We should confirm that we get valid information

    return state



def validation_complete(state: PayrollServiceGraphState) -> PayrollServiceGraphState:
    log.info("Input validation complete for client: TKTKTKTK")
    return state
