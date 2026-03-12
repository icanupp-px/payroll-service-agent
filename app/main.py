from fastapi import FastAPI

from app.api.routes import router as api_router
from app.payroll_service_agent.config.config import settings


def create_app() -> FastAPI:
    application = FastAPI(title="payroll-service-agent", version="0.1.0")
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
