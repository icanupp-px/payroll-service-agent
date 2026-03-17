
class PayrollStatusLookupUtils:
    @staticmethod
    def find_payperiod_status_value(data: object) -> str | None:
        if isinstance(data, dict):
            value = data.get("payPeriodStatusValue")
            if isinstance(value, str) and value.strip():
                return value
            for nested_value in data.values():
                found = PayrollStatusLookupUtils.find_payperiod_status_value(nested_value)
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = PayrollStatusLookupUtils.find_payperiod_status_value(item)
                if found:
                    return found
        return None

    @staticmethod
    def extract_payperiod_status_from_payload(
        payload: object, requested_payperiod_id: str
    ) -> str | None:
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

    @staticmethod
    def extract_check_date_for_payperiod_id(
        payload: object, requested_payperiod_id: str
    ) -> str | None:
        if not isinstance(payload, dict):
            return None

        content = payload.get("content")
        if not isinstance(content, dict):
            return None

        pay_periods = content.get("payPeriods")
        if not isinstance(pay_periods, list):
            return None

        for item in pay_periods:
            if not isinstance(item, dict):
                continue
            if str(item.get("payPeriodId")) != requested_payperiod_id:
                continue
            check_date = item.get("checkDate")
            if isinstance(check_date, str) and check_date.strip():
                return check_date

        return None

    @staticmethod
    def extract_payperiod_statuses_by_check_date(
        payload: object, requested_check_date: str
    ) -> list[str]:
        if not isinstance(payload, dict):
            return []

        content = payload.get("content")
        if not isinstance(content, dict):
            return []

        pay_periods = content.get("payPeriods")
        if not isinstance(pay_periods, list):
            return []

        statuses: list[str] = []
        for item in pay_periods:
            if not isinstance(item, dict):
                continue
            if str(item.get("checkDate")) != requested_check_date:
                continue
            value = item.get("payPeriodStatusValue")
            if isinstance(value, str) and value.strip() and value not in statuses:
                statuses.append(value)

        return statuses

    @staticmethod
    def extract_payperiod_status_map(payload: object) -> dict[str, str]:
        if not isinstance(payload, dict):
            return {}

        content = payload.get("content")
        if not isinstance(content, dict):
            return {}

        pay_periods = content.get("payPeriods")
        if not isinstance(pay_periods, list):
            return {}

        status_by_id: dict[str, str] = {}
        for item in pay_periods:
            if not isinstance(item, dict):
                continue
            payperiod_id = item.get("payPeriodId")
            value = item.get("payPeriodStatusValue")
            if payperiod_id is None:
                continue
            if isinstance(value, str) and value.strip():
                status_by_id[str(payperiod_id)] = value

        return status_by_id

    @staticmethod
    def extract_payperiod_status_map_by_check_date(
        payload: object, requested_check_date: str
    ) -> dict[str, str]:
        full_map = PayrollStatusLookupUtils.extract_payperiod_status_map(payload)
        if not full_map:
            return {}

        if not isinstance(payload, dict):
            return {}
        content = payload.get("content")
        if not isinstance(content, dict):
            return {}
        pay_periods = content.get("payPeriods")
        if not isinstance(pay_periods, list):
            return {}

        filtered: dict[str, str] = {}
        for item in pay_periods:
            if not isinstance(item, dict):
                continue
            if str(item.get("checkDate")) != requested_check_date:
                continue
            payperiod_id = item.get("payPeriodId")
            if payperiod_id is None:
                continue
            mapped = full_map.get(str(payperiod_id))
            if mapped:
                filtered[str(payperiod_id)] = mapped

        return filtered

    @staticmethod
    def extract_payperiod_status_map_by_event_time_and_check_date(
        payload: object, requested_check_date: str
    ) -> dict[str, str]:
        if not isinstance(payload, dict):
            return {}

        content = payload.get("content")
        if not isinstance(content, dict):
            return {}

        pay_periods = content.get("payPeriods")
        if not isinstance(pay_periods, list):
            return {}

        status_by_event_time: dict[str, str] = {}
        for item in pay_periods:
            if not isinstance(item, dict):
                continue
            if str(item.get("checkDate")) != requested_check_date:
                continue
            event_time = item.get("payPeriodStatusEventTime")
            status_value = item.get("payPeriodStatusValue")
            if not isinstance(event_time, str) or not event_time.strip():
                continue
            if isinstance(status_value, str) and status_value.strip():
                status_by_event_time[event_time] = status_value

        return status_by_event_time