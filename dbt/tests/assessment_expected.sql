-- Fixture checks apply only to this frozen assignment's Final snapshot.
{% if var('verify_assignment_final', true) %}
select 'final_result_mismatch' as failure
where (select count(*) from {{ ref('fact_strike') }}) <> 25518
   or (select count(*) from {{ ref('reporting_strikes') }} where airport='DALLAS/FORT WORTH INTL ARPT') <> 803
   or (select sum(cost) from {{ ref('reporting_strikes') }} where species='Canada goose') <> 20664597
{% else %}
select 'disabled' as failure where 1=0
{% endif %}
