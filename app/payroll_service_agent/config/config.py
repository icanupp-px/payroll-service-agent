from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "payroll-service-agent"
    environment: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    payroll_status_api_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("PAYROLL_STATUS_API_BASE_URL", "payroll_status_api_base_url"),
    )
    payroll_status_api_timeout_s: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "PAYROLL_STATUS_API_TIMEOUT_S", "payroll_status_api_timeout_s"
        ),
    )
    payroll_status_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PAYROLL_STATUS_API_KEY", "payroll_status_api_key"),
    )
    payroll_status_api_consumer: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PAYROLL_STATUS_API_CONSUMER", "payroll_status_api_consumer"
        ),
    )
    payroll_status_api_x_payx_cnsmr: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PAYROLL_STATUS_API_X_PAYX_CNSMR", "payroll_status_api_x_payx_cnsmr"
        ),
    )

    payroll_status_api_verify_ssl: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "PAYROLL_STATUS_API_VERIFY_SSL", "payroll_status_api_verify_ssl"
        ),
    )
    payroll_status_api_ca_bundle_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PAYROLL_STATUS_API_CA_BUNDLE_PATH", "payroll_status_api_ca_bundle_path"
        ),
    )


settings = Settings()
