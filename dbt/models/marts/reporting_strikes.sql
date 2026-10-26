{% set rate = var('aud_per_usd', none) %}
{% set rate_date = var('fx_rate_date', '') %}
{% set rate_source = var('fx_rate_source', '') %}
{% if rate is not none and (rate | float <= 0 or rate_date == '' or rate_source == '') %}
  {{ exceptions.raise_compiler_error('AUD reporting requires a positive aud_per_usd, fx_rate_date and fx_rate_source') }}
{% endif %}
select *,
  'USD assumed; awaiting confirmation' as source_currency_status,
  {% if rate is not none %}
  round(cost * {{ rate | float }}, 2) as cost_aud,
  cast('{{ rate_date | replace("'", "''") }}' as date) as fx_rate_date,
  '{{ rate_source | replace("'", "''") }}' as fx_rate_source
  {% else %}
  cast(null as decimal(38,2)) as cost_aud,
  cast(null as date) as fx_rate_date,
  cast(null as varchar) as fx_rate_source
  {% endif %}
from {{ ref('stg_strikes') }}
