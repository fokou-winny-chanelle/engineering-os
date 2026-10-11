-- One row per payment attempt. Rename and cast only; no business logic here.
select
    payment_id,
    merchant_id,
    cast(amount_xaf as bigint) as amount_xaf,
    lower(status) as status,
    cast(created_at as timestamp) as created_at,
    cast(created_at as date) as payment_date
from {{ ref('raw_payments') }}
