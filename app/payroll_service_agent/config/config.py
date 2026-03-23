from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=False,
        extra="ignore",
    )

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
    crossapp_mappings_api_url: str = Field(
        default="https://ca-ose-crossappmappings-v1-svc-pyx.n2a-lb.paychex.com/crossappmappings",
        validation_alias=AliasChoices(
            "CROSSAPP_MAPPINGS_API_URL", "crossapp_mappings_api_url"
        ),
    )
    crossapp_mappings_api_timeout_s: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "CROSSAPP_MAPPINGS_API_TIMEOUT_S", "crossapp_mappings_api_timeout_s"
        ),
    )
    crossapp_mappings_api_verify_ssl: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "CROSSAPP_MAPPINGS_API_VERIFY_SSL", "crossapp_mappings_api_verify_ssl"
        ),
    )
    crossapp_mappings_api_ca_bundle_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CROSSAPP_MAPPINGS_API_CA_BUNDLE_PATH", "crossapp_mappings_api_ca_bundle_path"
        ),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            dotenv_settings,
            init_settings,
            env_settings,
            file_secret_settings,
        )


settings = Settings()
