from pathlib import Path

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

    PAYROLL_STATUS_API_BASE_URL: str = ""
    PAYROLL_STATUS_API_TIMEOUT_S: float = 10.0
    PAYROLL_STATUS_API_KEY: str | None = None
    PAYROLL_STATUS_API_CONSUMER: str | None = None
    PAYROLL_STATUS_API_X_PAYX_CNSMR: str | None = None
    PAYROLL_STATUS_API_VERIFY_SSL: bool = True
    PAYROLL_STATUS_API_CA_BUNDLE_PATH: str | None = None

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
