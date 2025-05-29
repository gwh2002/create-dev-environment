-- Copy canonical company names table for anonymization lookups
-- Parameters:
--   {source_table} - Full source table name (project.dataset.canonical_company_names_sa)
--   {target_table} - Full target table name (project.dataset.canonical_company_names_sa)

CREATE OR REPLACE TABLE `{target_table}` AS 
SELECT * FROM `{source_table}` 