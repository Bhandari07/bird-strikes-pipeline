select record_id from {{ ref('fact_strike') }}
where cost<0 or injuries<0 or birds_struck<0 or feet_above_ground<0
   or damage not in (0,1) or pilot_warned not in (0,1)
