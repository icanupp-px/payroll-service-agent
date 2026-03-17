def find_payperiod_status_value(data: object) -> str | None:
    if isinstance(data, dict):
        value = data.get("payPeriodStatusValue")
        if isinstance(value, str) and value.strip():
            return value
        for nested_value in data.values():
            found = find_payperiod_status_value(nested_value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_payperiod_status_value(item)
            if found:
                return found
    return None


def extract_payperiod_status_from_payload(payload: object, requested_payperiod_id: str) -> str | None:
    if not isinstance(payload, dict):
        return None

    content = payload.get("content")
    if not isinstance(content, dict):
        return None

    pay_periods = content.get("payPeriods")
    if not isinstance(pay_periods, list):
        return None

    # Prefer the matching payPeriodId when present.
    for item in pay_periods:
        if not isinstance(item, dict):
            continue
        if str(item.get("payPeriodId")) == requested_payperiod_id:
            value = item.get("payPeriodStatusValue")
            if isinstance(value, str) and value.strip():
                return value

    # Otherwise, return the first non-empty payPeriodStatusValue in the list.
    for item in pay_periods:
        if not isinstance(item, dict):
            continue
        value = item.get("payPeriodStatusValue")
        if isinstance(value, str) and value.strip():
            return value

    return None
