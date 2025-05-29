-- Copy table with company name anonymization
-- Parameters:
--   {source_table} - Full source table name (project.dataset.table)
--   {target_table} - Full target table name (project.dataset.table)
--   {canonical_table} - Full canonical names table (project.dataset.canonical_company_names_sa)

CREATE OR REPLACE TABLE `{target_table}` AS
SELECT 
  CASE 
    WHEN ccn.public_company_name IS NOT NULL 
    THEN ccn.public_company_name 
    ELSE src.company_name 
  END as company_name,
  src.* EXCEPT(company_name)
FROM `{source_table}` src
LEFT JOIN `{canonical_table}` ccn
  ON src.company_name = ccn.company_name 