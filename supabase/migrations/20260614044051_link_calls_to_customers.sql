alter table calls
  add column customer_id   integer references customers(id) on delete set null,
  add column customer_name text;