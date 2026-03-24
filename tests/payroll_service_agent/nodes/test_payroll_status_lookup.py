import io
from urllib.error import HTTPError

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes import payroll_status_lookup as node


def test_fetch_status_by_check_date_sets_status_map(monkeypatch) -> None:
    payload = {
        "content": {
            "payPeriods": [
                {
                    "payPeriodId": "PP-1",
                    "checkDate": "2025-03-31",
                    "payPeriodStatusValue": "Initial",
                    "payPeriodStatusEventTime": "2025-03-31T10:11:12Z",
                },
                {
                    "payPeriodId": "PP-2",
                    "checkDate": "2025-03-31",
                    "payPeriodStatusValue": "Completed by MEC",
                    "payPeriodStatusEventTime": "2025-03-31T12:30:00Z",
                },
            ]
        }
    }

    monkeypatch.setattr(
        node.PayrollApiUtils,
        "fetch_payperiods_payload",
        lambda *args, **kwargs: payload,
    )

    state = PayrollServiceGraphState(
        request_id="req-1",
        metadata={
            "x-payx-cnsmr": "unit-test-consumer",
            "userguid": "u-1",
            "cltacctnbrs": "ENT:ABC123",
            "asof": "2025-03-31",
        },
    )

    updated = node.fetch_status_by_check_date(state)

    assert updated.status == "Completed by MEC"
    assert updated.payperiod_status_by_event_time == {
        "2025-03-31T12:30:00Z": "Completed by MEC",
    }


def test_fetch_status_by_check_date_sets_error_when_mocked_api_http_error(monkeypatch) -> None:
    def mock_fetch_payperiods_payload(*args, **kwargs):
        raise HTTPError(
            url="https://example.test/payperiods",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"upstream failure"}'),
        )

    monkeypatch.setattr(
        node.PayrollApiUtils,
        "fetch_payperiods_payload",
        mock_fetch_payperiods_payload,
    )

    state = PayrollServiceGraphState(
        request_id="req-2",
        metadata={
            "x-payx-cnsmr": "unit-test-consumer",
            "userguid": "u-2",
            "cltacctnbrs": "ENT:XYZ789",
            "asof": "2025-03-31",
        },
    )

    updated = node.fetch_status_by_check_date(state)

    assert updated.status == "error"


def test_select_payroll_status_branch_prefers_current_payroll_flow() -> None:
    state = PayrollServiceGraphState(
        request_id="req-3",
        flow_type="current_payroll",
        metadata={"asof": "2025-03-31"},
    )

    assert node._select_payroll_status_branch(state) == "fetch_status_by_current_payroll"


def test_select_payroll_status_branch_uses_check_date_when_present() -> None:
    state = PayrollServiceGraphState(
        request_id="req-4",
        metadata={"checkDate": "2025-03-31"},
    )

    assert node._select_payroll_status_branch(state) == "fetch_status_by_check_date"
