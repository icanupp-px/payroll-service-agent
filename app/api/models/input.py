from pydantic import BaseModel


class ProcessRequest(BaseModel):
    request_id: str
    payperiod_id: str
    metadata: dict[str, str] | None = None


class ProcessResponse(BaseModel):
    request_id: str
    status: str
    payperiod_status: str | None = None
    payperiod_holds: list | None = None
