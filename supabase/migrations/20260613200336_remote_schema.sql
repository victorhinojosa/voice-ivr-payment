create table if not exists calls (
    id               serial primary key,
    call_sid         text,
    phone_number     text not null,
    status           text default 'initiated',
    outcome          text,
    amount_owed      numeric(10,2),
    promise_date     date,
    promise_amount   numeric(10,2),
    transcript       text,
    duration_seconds integer,
    initiated_at     timestamp default current_timestamp,
    completed_at     timestamp
);

create table if not exists config (
    key   text primary key,
    value text not null
);