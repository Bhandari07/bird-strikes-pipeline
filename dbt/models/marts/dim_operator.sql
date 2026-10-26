select distinct {{ dimension_key(['operator']) }} as operator_key, operator
from {{ ref('stg_strikes') }}
