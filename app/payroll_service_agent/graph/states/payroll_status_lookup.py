from pydantic import BaseModel


class PayrollServiceGraphState(BaseModel):
    request_id: str
    payperiod_id: str | None = None
    metadata: dict[str, str] | None = None
    status: str | None = None
    holds: list[dict] | None = None  # Holds info from API
