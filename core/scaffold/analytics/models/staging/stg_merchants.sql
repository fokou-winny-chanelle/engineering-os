select
    merchant_id,
    merchant_name,
    upper(country) as country,
    cast(created_at as timestamp) as created_at
from {{ ref('raw_merchants') }}
