select distinct {{ dimension_key(['airport', 'state']) }} as airport_key, airport, state
from {{ ref('stg_strikes') }}
