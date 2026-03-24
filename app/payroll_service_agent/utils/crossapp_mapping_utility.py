import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.payroll_service_agent.config.config import settings
from app.payroll_service_agent.utils.llm_selection_utility import LlmSelectionUtility


INVALID_CLIENT_ACCOUNT_MESSAGE = "Please send a valid Client Account number"


class CrossAppMappingUtility:
    ENT_ID_PATTERN = re.compile(r"\bENT:\s*[A-Za-z0-9]+\b", re.IGNORECASE)
    CA_CLIENT_ACCOUNT_PATTERN = re.compile(r"^(?:CA:)?[A-Za-z0-9]+$", re.IGNORECASE)
    DEFAULT_X_PAYX_CNSMR = "CA DOMAIN"
    DEFAULT_USERGUID = "CA:12345"
    FALLBACK_USERGUID = "CA:751234564482"

    @staticmethod
    def resolve_payx_consumer(effective_metadata: dict[str, str]) -> str | None:
        return (
            effective_metadata.get("x-payx-cnsmr")
            or effective_metadata.get("x_payx_cnsmr")
            or effective_metadata.get("consumer")
            or effective_metadata.get("x-consumer")
            or effective_metadata.get("source")
            or CrossAppMappingUtility.DEFAULT_X_PAYX_CNSMR
            or settings.payroll_status_api_x_payx_cnsmr
            or settings.payroll_status_api_consumer
        )

    @staticmethod
    def _crossapp_ssl_context() -> ssl.SSLContext | None:
        if settings.crossapp_mappings_api_ca_bundle_path:
            return ssl.create_default_context(cafile=settings.crossapp_mappings_api_ca_bundle_path)
        if not settings.crossapp_mappings_api_verify_ssl:
            return ssl._create_unverified_context()  # dev-only
        return None

    @staticmethod
    def _fetch_crossapp_mapping_payload(
        userguid: str,
        ent_client_account: str,
        payx_consumer: str,
    ) -> object:
        if not settings.crossapp_mappings_api_url:
            raise ValueError(INVALID_CLIENT_ACCOUNT_MESSAGE)

        url = settings.crossapp_mappings_api_url.rstrip("/") + "?" + urlencode(
            {
                "userguid": userguid,
                "cltacctnbrs": ent_client_account,
            }
        )

        headers = {
            "Accept": "application/json",
            "x-payx-cnsmr": payx_consumer,
        }
        req = Request(url, headers=headers, method="GET")
        with urlopen(
            req,
            timeout=settings.crossapp_mappings_api_timeout_s,
            context=CrossAppMappingUtility._crossapp_ssl_context(),
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _extract_first_ca_client_account(payload: object) -> str | None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                normalized_key = str(key).strip().lower()
                if normalized_key == "caclientacctnbr":
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        return str(value).strip()
            for nested in payload.values():
                found = CrossAppMappingUtility._extract_first_ca_client_account(nested)
                if found:
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = CrossAppMappingUtility._extract_first_ca_client_account(item)
                if found:
                    return found
        return None

    @staticmethod
    def _extract_ca_client_account_via_llm(
        ent_client_account: str,
        crossapp_payload: object,
    ) -> str | None:
        deterministic_value = CrossAppMappingUtility._extract_first_ca_client_account(crossapp_payload)
        try:
            llm_value = LlmSelectionUtility.extract_ca_client_account(
                ent_client_account,
                crossapp_payload,
            )
            if isinstance(llm_value, str) and llm_value.strip():
                return llm_value
        except Exception:
            pass

        return deterministic_value

    @staticmethod
    def _normalize_ca_client_account(value: str) -> str | None:
        raw = (value or "").strip().upper()
        if not raw:
            return None
        if not CrossAppMappingUtility.CA_CLIENT_ACCOUNT_PATTERN.match(raw):
            return None
        if raw.startswith("CA:"):
            return raw
        return f"CA:{raw}"

    @staticmethod
    def resolve_ca_client_account_number(
        metadata: dict[str, str] | None,
        prompt: str | None,
    ) -> tuple[str | None, str | None]:
        effective_metadata = metadata or {}
        prompt_text = prompt or ""
        prompt_ent_match = CrossAppMappingUtility.ENT_ID_PATTERN.search(prompt_text)
        if prompt_text and not prompt_ent_match:
            return None, INVALID_CLIENT_ACCOUNT_MESSAGE

        ent_match = prompt_ent_match
        if not ent_match:
            return None, INVALID_CLIENT_ACCOUNT_MESSAGE

        userguid = effective_metadata.get("userguid") or CrossAppMappingUtility.DEFAULT_USERGUID
        if not userguid:
            return None, INVALID_CLIENT_ACCOUNT_MESSAGE

        payx_consumer = CrossAppMappingUtility.resolve_payx_consumer(effective_metadata)
        if not payx_consumer:
            return None, INVALID_CLIENT_ACCOUNT_MESSAGE

        ent_client_account = re.sub(r"\s+", "", ent_match.group(0).upper())
        attempted_userguids: list[str] = []
        for candidate_userguid in [userguid, CrossAppMappingUtility.FALLBACK_USERGUID]:
            if not candidate_userguid or candidate_userguid in attempted_userguids:
                continue
            attempted_userguids.append(candidate_userguid)
            try:
                crossapp_payload = CrossAppMappingUtility._fetch_crossapp_mapping_payload(
                    userguid=candidate_userguid,
                    ent_client_account=ent_client_account,
                    payx_consumer=payx_consumer,
                )
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
                continue

            ca_client_acct_nbr = CrossAppMappingUtility._extract_ca_client_account_via_llm(
                ent_client_account,
                crossapp_payload,
            )
            if not isinstance(ca_client_acct_nbr, str):
                continue

            normalized = CrossAppMappingUtility._normalize_ca_client_account(ca_client_acct_nbr)
            if not normalized:
                continue

            return normalized, None

        return None, INVALID_CLIENT_ACCOUNT_MESSAGE
