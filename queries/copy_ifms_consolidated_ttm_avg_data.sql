-- Copy IFMS Consolidated TTM Average Data table - customize anonymization logic as needed
-- Parameters:
--   {source_table} - Full source table name (project.dataset.ifms_consolidated_ttm_avg_data)
--   {target_table} - Full target table name (project.dataset.ifms_consolidated_ttm_avg_data)
--   {source_project} - Source project ID
--   {source_dataset} - Source dataset name
--   {target_project} - Target project ID 
--   {target_dataset} - Target dataset name
--   {table_name} - Table name (ifms_consolidated_ttm_avg_data)

-- TODO: Define your custom anonymization logic here
-- TTM data may be aggregated and need different handling

CREATE OR REPLACE TABLE `{target_table}` AS
SELECT * FROM `{source_table}`

-- REPLACE THE ABOVE WITH YOUR CUSTOM LOGIC 