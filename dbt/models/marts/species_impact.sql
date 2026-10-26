select species,count(*) as incidents,sum(cost) as total_reported_cost,
 sum(damage) as damaged_incidents, sum(case when cost>0 then 1 else 0 end) as positive_cost_incidents
from {{ ref('reporting_strikes') }} group by species
