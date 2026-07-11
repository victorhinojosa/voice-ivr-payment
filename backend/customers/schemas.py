from datetime import datetime
from pydantic import BaseModel

class CustomerBase(BaseModel):
    name: str
    phone: str
    amount_owed: float = 0
    status: str = "active"

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):      
    name: str | None = None
    phone: str | None = None
    amount_owed: float | None = None
    status: str | None = None

class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime