from pydantic import BaseModel, Field, model_validator


class ProcessRequest(BaseModel):
    request_id: str
    prompt: str | None = None
    check_date: str | None = None
    metadata: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_request_scope(self) -> "ProcessRequest":
        if not self.check_date:
            raise ValueError(
                "Please provide checkdate to get the payroll status"
            )
        return self


class ProcessResponse(BaseModel):
    request_id: str
    payperiod_status: str | None = None
    payroll_status_by_submit_time: dict[str, str] | None = Field(
        default=None,
        serialization_alias="payrollStatusBySubmitTime",
    )
    payperiod_holds: list | None = None
