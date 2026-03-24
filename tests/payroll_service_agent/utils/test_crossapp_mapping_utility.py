from app.payroll_service_agent.utils.crossapp_mapping_utility import (
    CrossAppMappingUtility,
    INVALID_CLIENT_ACCOUNT_MESSAGE,
)


def test_resolve_payx_consumer_prefers_metadata_value() -> None:
    consumer = CrossAppMappingUtility.resolve_payx_consumer(
        {
            "x-payx-cnsmr": "metadata-consumer",
            "consumer": "fallback-consumer",
        }
    )

    assert consumer == "metadata-consumer"


def test_extract_first_ca_client_account_handles_nested_numeric_values() -> None:
    payload = {
        "content": {
            "crossappmappings": [
                {
                    "details": {
                        "caClientAcctNbr": 751234,
                    }
                }
            ]
        }
    }

    result = CrossAppMappingUtility._extract_first_ca_client_account(payload)

    assert result == "751234"


def test_resolve_ca_client_account_number_requires_ent_prompt() -> None:
    resolved_value, error = CrossAppMappingUtility.resolve_ca_client_account_number(
        metadata={"userguid": "u-1", "x-payx-cnsmr": "consumer-1"},
        prompt="status for CA:12345",
    )

    assert resolved_value is None
    assert error == INVALID_CLIENT_ACCOUNT_MESSAGE


def test_resolve_ca_client_account_number_uses_payload_and_normalizes(monkeypatch) -> None:
    payload = {
        "content": {
            "crossappmappings": [
                {
                    "caClientAcctNbr": "751234",
                }
            ]
        }
    }

    monkeypatch.setattr(
        CrossAppMappingUtility,
        "_fetch_crossapp_mapping_payload",
        lambda **kwargs: payload,
    )

    resolved_value, error = CrossAppMappingUtility.resolve_ca_client_account_number(
        metadata={"userguid": "u-1", "x-payx-cnsmr": "consumer-1"},
        prompt="status for ENT:ABC123",
    )

    assert resolved_value == "CA:751234"
    assert error is None