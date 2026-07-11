from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class CallBase(BaseModel):
    phone_number: str
    amount_owed: float
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None

class CallCreate(CallBase):
    pass

class CallResponse(CallBase):
    id: int
    call_sid: str | None = None
    status: str
    outcome: str | None = None
    promise_date: date | None = None
    promise_amount: float | None = None
    transcript: str | None = None
    duration_seconds: int | None = None
    initiated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
