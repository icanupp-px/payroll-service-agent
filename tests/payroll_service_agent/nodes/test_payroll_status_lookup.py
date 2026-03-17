import io
import json
from urllib.error import HTTPError

from app.payroll_service_agent.graph.states.payroll_status_lookup import PayrollServiceGraphState
from app.payroll_service_agent.nodes import payroll_status_lookup as node


class _MockResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_fetch_status_sets_status_from_mocked_api(monkeypatch) -> None:
    monkeypatch.setattr(node.settings, "payroll_status_api_base_url", "https://example.test")
    monkeypatch.setattr(node.settings, "payroll_status_api_timeout_s", 5.0)
    monkeypatch.setattr(node.settings, "payroll_status_api_key", None)
    monkeypatch.setattr(node.settings, "payroll_status_api_verify_ssl", True)
    monkeypatch.setattr(node.settings, "payroll_status_api_ca_bundle_path", None)

    payload = {
        "content": {
            "payPeriods": [
                {"payPeriodId": "PP-123", "payPeriodStatusValue": "Completed"}
            ]
        }
    }

    def mock_urlopen(req, timeout, context):
        assert req.full_url.startswith("https://example.test/payperiods/PP-123?")
        return _MockResponse(payload)

    monkeypatch.setattr(node, "urlopen", mock_urlopen)

    state = PayrollServiceGraphState(
        request_id="req-1",
        payperiod_id="PP-123",
        metadata={"x-payx-cnsmr": "unit-test-consumer", "userguid": "u-1", "cltacctnbrs": "c-1"},
    )

    updated = node.fetch_status(state)

    assert updated.status == "Completed"


def test_fetch_status_sets_error_when_mocked_api_http_error(monkeypatch) -> None:
    monkeypatch.setattr(node.settings, "payroll_status_api_base_url", "https://example.test")
    monkeypatch.setattr(node.settings, "payroll_status_api_timeout_s", 5.0)
    monkeypatch.setattr(node.settings, "payroll_status_api_key", None)
    monkeypatch.setattr(node.settings, "payroll_status_api_verify_ssl", True)
    monkeypatch.setattr(node.settings, "payroll_status_api_ca_bundle_path", None)

    def mock_urlopen(req, timeout, context):
        raise HTTPError(
            url=req.full_url,
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"upstream failure"}'),
        )

    monkeypatch.setattr(node, "urlopen", mock_urlopen)

    state = PayrollServiceGraphState(
        request_id="req-2",
        payperiod_id="PP-500",
        metadata={"x-payx-cnsmr": "unit-test-consumer", "userguid": "u-2", "cltacctnbrs": "c-2"},
    )

    updated = node.fetch_status(state)

    assert updated.status == "error"
