select distinct {{ dimension_key(['sky', 'precipitation', 'has_rain', 'has_fog', 'has_snow']) }} as weather_key, sky, precipitation, has_rain, has_fog, has_snow
from {{ ref('stg_strikes') }}
