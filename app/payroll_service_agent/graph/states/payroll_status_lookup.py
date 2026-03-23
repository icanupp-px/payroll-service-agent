from pydantic import BaseModel


class PayrollServiceGraphState(BaseModel):
    request_id: str
    prompt: str | None = None
    metadata: dict[str, str] | None = None
    status: str | None = None
    payperiod_status_by_event_time: dict[str, str] | None = None
    result: str | None = None
    holds: list[dict] | None = None  # Holds info from API
