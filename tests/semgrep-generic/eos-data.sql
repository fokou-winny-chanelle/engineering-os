CREATE TABLE orders (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  -- ruleid: eos-money-float-sql
  amount double precision NOT NULL,
  -- ruleid: eos-money-float-sql
  "total_price" real,
  -- ruleid: eos-money-float-sql
  fee money,
  -- ok: eos-money-float-sql
  price numeric(12, 2) NOT NULL,
  -- ok: eos-money-float-sql
  discount_percent real,
  -- ok: eos-money-float-sql
  latitude double precision
);
-- ruleid: eos-money-float-sql
ALTER TABLE orders ADD COLUMN tax_amount float8;
-- ok: eos-money-float-sql
ALTER TABLE orders ADD COLUMN tax_rate double precision;
-- ruleid: eos-money-float-sql
ALTER TABLE orders ADD COLUMN account_balance real;
