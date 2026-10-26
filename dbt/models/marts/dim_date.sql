select distinct {{ dimension_key(['flight_date']) }} as date_key, flight_date, extract(year from flight_date) as year, extract(month from flight_date) as month, extract(quarter from flight_date) as quarter
from {{ ref('stg_strikes') }}
