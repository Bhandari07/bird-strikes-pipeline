select distinct {{ dimension_key(['aircraft_type', 'aircraft_model']) }} as aircraft_key, aircraft_type, aircraft_model
from {{ ref('stg_strikes') }}
