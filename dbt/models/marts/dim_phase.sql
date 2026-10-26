select distinct {{ dimension_key(['phase']) }} as phase_key, phase
from {{ ref('stg_strikes') }}
