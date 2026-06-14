from core.database import get_pool
from customers.schemas import CustomerCreate, CustomerOut, CustomerUpdate

async def create_customer(customer: CustomerCreate) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO customers (name, phone, amount_owed, status)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, customer.name, customer.phone, customer.amount_owed, customer.status)
        return dict(row)

async def update_customer(customer_id: int, customer: CustomerUpdate) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE customers
            SET name        = COALESCE($2, name),
                phone       = COALESCE($3, phone),
                amount_owed = COALESCE($4, amount_owed),
                status      = COALESCE($5, status),
                updated_at  = now()
            WHERE id = $1
            RETURNING *
        """, customer_id, customer.name, customer.phone, customer.amount_owed, customer.status)
        return dict(row) if row else None

async def delete_customer(customer_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM customers WHERE id = $1 RETURNING id", customer_id)
        return row is not None

async def get_all_customers() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM customers")
        return [dict(row) for row in rows]

async def get_customer_by_id(customer_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM customers WHERE id = $1", customer_id)
        return dict(row) if row else None

