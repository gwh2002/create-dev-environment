create or replace table `deconstructed-logos.risk.risk_rating_all_time_historical` as (
select 
    ccn.public_company_name as company_name,
    rr.* EXCEPT(company_name)
from `assembled-wh.warehouse.risk_rating_all_time_historical` rr
left join `assembled-wh.warehouse.canonical_company_names_sa` ccn
    on rr.company_name = ccn.company_name
)