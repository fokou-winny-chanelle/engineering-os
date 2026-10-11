select merchant_id, merchant_name, country, created_at
from {{ ref('stg_merchants') }}
