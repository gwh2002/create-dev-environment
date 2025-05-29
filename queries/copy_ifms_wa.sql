-- Copy IFMS WA table - customize anonymization logic as needed
-- Parameters:
--   {source_table} - Full source table name (project.dataset.ifms_wa)
--   {target_table} - Full target table name (project.dataset.ifms_wa)
--   {source_project} - Source project ID
--   {source_dataset} - Source dataset name
--   {target_project} - Target project ID 
--   {target_dataset} - Target dataset name
--   {table_name} - Table name (ifms_wa)

-- TODO: Define your custom anonymization logic here
-- WA-specific data may have different anonymization requirements

CREATE OR REPLACE TABLE `{target_table}` AS
SELECT * FROM `{source_table}`

-- REPLACE THE ABOVE WITH YOUR CUSTOM LOGIC 