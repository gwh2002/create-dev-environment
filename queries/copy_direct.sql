-- Copy table directly without anonymization
-- Use this for tables that don't have a company_name column
-- Parameters:
--   {source_table} - Full source table name (project.dataset.table)
--   {target_table} - Full target table name (project.dataset.table)

CREATE OR REPLACE TABLE `{target_table}` AS
SELECT * FROM `{source_table}` 