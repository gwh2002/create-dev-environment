-- Copy IFMS Consolidated table - customize anonymization logic as needed
-- Parameters:
--   {source_table} - Full source table name (project.dataset.ifms_consolidated)
--   {target_table} - Full target table name (project.dataset.ifms_consolidated)
--   {source_project} - Source project ID
--   {source_dataset} - Source dataset name
--   {target_project} - Target project ID 
--   {target_dataset} - Target dataset name
--   {table_name} - Table name (ifms_consolidated)

-- TODO: Define your custom anonymization logic here
-- This table may have different column names or structures than ifms

CREATE OR REPLACE TABLE `{target_table}` AS
SELECT * FROM `{source_table}`

-- REPLACE THE ABOVE WITH YOUR CUSTOM LOGIC 