
from pydantic import BaseModel

class ParsedPayrollRequest(BaseModel):
    client_id: str | None = None
    check_date: str | None = None
    payperiod_id: str | None = None