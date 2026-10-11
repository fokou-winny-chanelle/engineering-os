-- Grain: one row per merchant per UTC day. Sums are cast back to bigint so the contract's types hold.
select
    merchant_id || '|' || strftime(payment_date, '%Y-%m-%d') as merchant_day_key,
    merchant_id,
    payment_date,
    count(*) as attempts,
    cast(count(*) filter (where status = 'succeeded') as bigint) as succeeded_count,
    cast(coalesce(sum(amount_xaf) filter (where status = 'succeeded'), 0) as bigint) as succeeded_amount_xaf,
    cast(coalesce(sum(amount_xaf) filter (where status = 'refunded'), 0) as bigint) as refunded_amount_xaf
from {{ ref('stg_payments') }}
group by merchant_id, payment_date
