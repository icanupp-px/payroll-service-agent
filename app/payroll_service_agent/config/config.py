
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

    payroll_status_api_base_url: str = ""
    payroll_status_api_timeout_s: float = 10.0
    payroll_status_api_key: str | None = None
    payroll_status_api_consumer: str | None = None
    payroll_status_api_x_payx_cnsmr: str | None = None
    payroll_status_api_verify_ssl: bool = True
    payroll_status_api_ca_bundle_path: str | None = None

    # Holds API config
    payroll_holds_api_base_url: str = ""
    payroll_holds_api_timeout_s: float = 10.0
    payroll_holds_api_key: str | None = None
    payroll_holds_api_consumer: str | None = None
    payroll_holds_api_x_payx_cnsmr: str | None = None
    payroll_holds_api_verify_ssl: bool = True
    payroll_holds_api_ca_bundle_path: str | None = None


settings = Settings()
