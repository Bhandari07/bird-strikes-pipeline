select 'row_count_mismatch' as failure
where (select count(*) from {{ ref('fact_strike') }}) <>
      (select count(*) from {{ source('ingestion','strike_current') }})
