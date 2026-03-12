from pydantic import BaseModel


class PayrollServiceGraphState(BaseModel):
    request_id: str
    payperiod_id: str | None = None
    status: str | None = None
    result: str | None = None
