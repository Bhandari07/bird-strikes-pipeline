select distinct {{ dimension_key(['species', 'wildlife_size']) }} as wildlife_key, species, wildlife_size
from {{ ref('stg_strikes') }}
