select extract(year from flight_date) as year, count(*) as incidents
from {{ ref('reporting_strikes') }} where flight_date is not null group by 1
