from fastapi import APIRouter, HTTPException
from customers import repository
from customers.schemas import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["customers"])

@router.get("", response_model=list[CustomerResponse])
async def list_customers():
    return await repository.get_all_customers()

@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: int):
    customer = await repository.get_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(customer: CustomerCreate):
    return await repository.create_customer(customer)

@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: int, customer: CustomerUpdate):
    updated = await repository.update_customer(customer_id, customer)
    if updated is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return updated

@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: int):
    if not await repository.delete_customer(customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")