select 'quality_count_mismatch' as failure
where (select coalesce(sum(dq_issue_count),0) from {{ ref('fact_strike') }}) <>
      (select count(*) from {{ ref('quality_issues') }})
