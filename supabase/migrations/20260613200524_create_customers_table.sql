create table if not exists customers (
    id          serial primary key,
    name        text not null,
    phone       text not null,
    amount_owed numeric(10,2) not null default 0,
    status      text not null default 'active',
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);