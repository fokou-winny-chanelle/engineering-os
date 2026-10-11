-- Reconciliation: money in the mart must equal money in staging. Returns a row (= failure) when they differ.
with mart as (
    select coalesce(sum(succeeded_amount_xaf), 0) as total from {{ ref('fct_daily_payments') }}
),
src as (
    select coalesce(sum(amount_xaf), 0) as total from {{ ref('stg_payments') }} where status = 'succeeded'
)
select mart.total as mart_total, src.total as source_total
from mart cross join src
where mart.total <> src.total
