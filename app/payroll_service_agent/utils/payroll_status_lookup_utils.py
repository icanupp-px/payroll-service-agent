import json
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.utils.crossapp_mapping_utility import (
    CrossAppMappingUtility,
    INVALID_CLIENT_ACCOUNT_MESSAGE,
)
from app.payroll_service_agent.utils.llm_selection_utility import LlmSelectionUtility


class CurrentPayrollSelection(BaseModel):
    check_date: str | None = None
    submission_time: str | None = None
    status: str | None = None


class PayrollStatusLookupUtils:
    OMITTED_STATUSES = {"ENTRY", "INITIAL"}

    @staticmethod
    def is_allowed_status(value: str | None) -> bool:
        if not isinstance(value, str):
            return False
        return value.strip().upper() not in PayrollStatusLookupUtils.OMITTED_STATUSES

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


class PayrollApiUtils:
    ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY = (
        "Completed,Completed by MEC,Processing,Reissued,Released,Reversed,Time Delay"
    )
    DEFAULT_PROJECTION = "payperiod"
    DEFAULT_PAGE = "0"

    @staticmethod
    def _default_current_checkdate_asof() -> str:
        return (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()

    @staticmethod
    def fetch_payperiods_payload(
        metadata: dict[str, str] | None,
        requested_check_date: str | None = None,
        prompt: str | None = None,
    ) -> object:
        if not settings.payroll_status_api_base_url:
            raise ValueError("PAYROLL_STATUS_API_BASE_URL not set")

        effective_metadata = metadata or {}
        payx_consumer = CrossAppMappingUtility.resolve_payx_consumer(effective_metadata)
        if not payx_consumer:
            raise ValueError(
                "Missing required x-payx-cnsmr value. "
                "Set metadata.x-payx-cnsmr or PAYROLL_STATUS_API_X_PAYX_CNSMR."
            )

        resolved_client_account, resolution_error = CrossAppMappingUtility.resolve_ca_client_account_number(
            effective_metadata,
            prompt,
        )
        if resolution_error or not resolved_client_account:
            raise ValueError(INVALID_CLIENT_ACCOUNT_MESSAGE)

        query = {
            "status": PayrollApiUtils.ALL_PAYPERIOD_STATUSES_WITH_TIME_DELAY,
            "projection": PayrollApiUtils.DEFAULT_PROJECTION,
            "userguid": CrossAppMappingUtility.DEFAULT_USERGUID,
            "cltacctnbrs": resolved_client_account,
            "page": PayrollApiUtils.DEFAULT_PAGE,
        }
        if requested_check_date:
            query["asof"] = requested_check_date
            query["checkdateasof"] = requested_check_date
        else:
            query["checkdateasof"] = (
                effective_metadata.get("checkdateasof")
                or PayrollApiUtils._default_current_checkdate_asof()
            )
        query = {k: v for k, v in query.items() if v is not None}

        url = settings.payroll_status_api_base_url.rstrip("/") + "/payperiods?" + urlencode(query)

        headers = {
            "Accept": "application/json",
            "x-payx-cnsmr": payx_consumer,
        }
        if settings.payroll_status_api_key:
            headers["Authorization"] = f"Bearer {settings.payroll_status_api_key}"

        req = Request(url, headers=headers, method="GET")

        ssl_ctx = None
        if settings.payroll_status_api_ca_bundle_path:
            ssl_ctx = ssl.create_default_context(cafile=settings.payroll_status_api_ca_bundle_path)
        elif not settings.payroll_status_api_verify_ssl:
            ssl_ctx = ssl._create_unverified_context()  # dev-only

        with urlopen(req, timeout=settings.payroll_status_api_timeout_s, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))


class CurrentPayrollSelectionUtils:
    @staticmethod
    def extract_payperiod_candidates(payload: object) -> list[dict[str, str]]:
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
            if (
                not isinstance(status, str)
                or not status.strip()
                or not PayrollStatusLookupUtils.is_allowed_status(status)
            ):
                continue
            candidates.append(
                {
                    "checkDate": check_date,
                    "payPeriodStatusValue": status,
                    "payPeriodStatusEventTime": submission_time or "",
                }
            )
        return candidates

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime | None:
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

    @staticmethod
    def heuristic_current_selection(candidates: list[dict[str, str]]) -> CurrentPayrollSelection | None:
        if not candidates:
            return None

        now_utc = datetime.now(timezone.utc)

        def score(item: dict[str, str]) -> tuple[float, str, str]:
            event_time = CurrentPayrollSelectionUtils._parse_timestamp(
                item.get("payPeriodStatusEventTime", "")
            )
            if event_time is not None:
                delta_seconds = abs((event_time - now_utc).total_seconds())
                return (
                    delta_seconds,
                    item.get("payPeriodStatusEventTime", ""),
                    item.get("checkDate", ""),
                )
            return (float("inf"), "", item.get("checkDate", ""))

        closest = sorted(candidates, key=score)
        item = closest[0]
        return CurrentPayrollSelection(
            check_date=item.get("checkDate"),
            submission_time=item.get("payPeriodStatusEventTime") or item.get("checkDate"),
            status=item.get("payPeriodStatusValue"),
        )

    @staticmethod
    def llm_current_selection(prompt: str, candidates: list[dict[str, str]]) -> CurrentPayrollSelection | None:
        selection = LlmSelectionUtility.select_current_payroll(prompt, candidates)
        if not selection:
            return None
        return CurrentPayrollSelection(
            check_date=selection.check_date,
            submission_time=selection.submission_time,
            status=selection.status,
        )