from types import SimpleNamespace

from app.payroll_service_agent.utils.payroll_status_lookup_utils import (
    CurrentPayrollSelectionUtils,
    CurrentPayrollSelection,
    PayrollStatusLookupUtils,
)


def test_is_allowed_status_filters_entry_and_initial() -> None:
    assert PayrollStatusLookupUtils.is_allowed_status("Completed by MEC") is True
    assert PayrollStatusLookupUtils.is_allowed_status("ENTRY") is False
    assert PayrollStatusLookupUtils.is_allowed_status("Initial") is False


def test_extract_payperiod_candidates_omits_disallowed_and_invalid_items() -> None:
    payload = {
        "content": {
            "payPeriods": [
                {
                    "checkDate": "2025-03-31",
                    "payPeriodStatusValue": "Completed by MEC",
                    "payPeriodStatusEventTime": "2025-03-31T12:30:00Z",
                },
                {
                    "checkDate": "2025-03-31",
                    "payPeriodStatusValue": "Initial",
                    "payPeriodStatusEventTime": "2025-03-31T09:00:00Z",
                },
                {
                    "checkDate": "",
                    "payPeriodStatusValue": "Completed",
                    "payPeriodStatusEventTime": "2025-03-31T08:00:00Z",
                },
            ]
        }
    }

    result = CurrentPayrollSelectionUtils.extract_payperiod_candidates(payload)

    assert result == [
        {
            "checkDate": "2025-03-31",
            "payPeriodStatusValue": "Completed by MEC",
            "payPeriodStatusEventTime": "2025-03-31T12:30:00Z",
        }
    ]


def test_heuristic_current_selection_prefers_candidate_with_valid_event_time() -> None:
    candidates = [
        {
            "checkDate": "2025-03-31",
            "payPeriodStatusValue": "Processing",
            "payPeriodStatusEventTime": "",
        },
        {
            "checkDate": "2025-04-01",
            "payPeriodStatusValue": "Completed",
            "payPeriodStatusEventTime": "2025-04-01T10:00:00Z",
        },
    ]

    result = CurrentPayrollSelectionUtils.heuristic_current_selection(candidates)

    assert result == CurrentPayrollSelection(
        check_date="2025-04-01",
        submission_time="2025-04-01T10:00:00Z",
        status="Completed",
    )


def test_llm_current_selection_maps_llm_utility_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.payroll_service_agent.utils.payroll_status_lookup_utils.LlmSelectionUtility.select_current_payroll",
        lambda prompt, candidates: SimpleNamespace(
            check_date="2025-04-15",
            submission_time="2025-04-15T14:00:00Z",
            status="Completed by MEC",
        ),
    )

    result = CurrentPayrollSelectionUtils.llm_current_selection(
        "current payroll status",
        [{"checkDate": "2025-04-15", "payPeriodStatusValue": "Completed by MEC"}],
    )

    assert result == CurrentPayrollSelection(
        check_date="2025-04-15",
        submission_time="2025-04-15T14:00:00Z",
        status="Completed by MEC",
    )