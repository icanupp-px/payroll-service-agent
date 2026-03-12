from fastapi import APIRouter

from app.api.models.input import ProcessRequest, ProcessResponse
from app.orchestrator import orchestrator

router = APIRouter()


@router.post("/process", response_model=ProcessResponse)
async def process(payload: ProcessRequest) -> ProcessResponse:
    return await orchestrator.orchestrate_payroll_service_processing(payload)
