# Queries Directory

This directory contains SQL template files that define how data is copied from production to contractor environments. **Each table has its own specific SQL file where you define custom anonymization logic.**

## How It Works

1. **Table-Specific SQL Files**: Each table has its own SQL file (e.g., `copy_ifms.sql`)
2. **Custom Anonymization**: You define the exact anonymization logic in each SQL file
3. **Parameter Substitution**: The Python script replaces placeholders like `{source_table}` with actual values
4. **Full Control**: Complete control over how each table is copied and anonymized

## Available Parameters

All SQL files can use these parameters:

- `{source_table}` - Full source table name (e.g., `assembled-wh.warehouse.ifms`)
- `{target_table}` - Full target table name (e.g., `partner-john-smith-dev-2025.warehouse.ifms`)
- `{source_project}` - Source project ID (e.g., `assembled-wh`)
- `{source_dataset}` - Source dataset name (e.g., `warehouse`)
- `{target_project}` - Target project ID (e.g., `partner-john-smith-dev-2025`)
- `{target_dataset}` - Target dataset name (e.g., `warehouse`)
- `{table_name}` - Just the table name without project/dataset (e.g., `ifms`)

## Current SQL Files

### Tables Requiring Custom Anonymization Logic
- `copy_ifms.sql` - Main IFMS data table (TODO: Add your anonymization logic)
- `copy_ifms_consolidated.sql` - Consolidated IFMS data (TODO: Add your anonymization logic)
- `copy_ifms_wa.sql` - IFMS WA-specific data (TODO: Add your anonymization logic)
- `copy_ifms_consolidated_ttm_avg_data.sql` - TTM average data (TODO: Add your anonymization logic)

### Generic Templates (for reference)
- `copy_direct.sql` - Simple copy without any transformation
- `copy_canonical_names.sql` - Example of copying a lookup table

## Adding New Tables

To add a new table:

1. **Create SQL file**: Create `copy_[table_name].sql` in this directory
2. **Define logic**: Write the SQL query with your custom anonymization approach
3. **Update config**: Add entry to `table_copy_configs` in `master_config.yaml`
4. **Add to defaults**: Add table name to `default_tables` in `master_config.yaml`

## Anonymization Approaches

You can implement different anonymization strategies in each SQL file:

### 1. Lookup Table Approach
```sql
-- If you have a lookup table for anonymization
CREATE OR REPLACE TABLE `{target_table}` AS
SELECT 
  COALESCE(lookup.anonymous_name, src.company_name) as company_name,
  src.* EXCEPT(company_name)
FROM `{source_table}` src
LEFT JOIN `{source_project}.{source_dataset}.company_anonymization_lookup` lookup
  ON src.company_name = lookup.real_name
```

### 2. Hash-Based Anonymization
```sql
-- Hash company names for anonymization
CREATE OR REPLACE TABLE `{target_table}` AS
SELECT 
  CONCAT('Company_', SUBSTR(TO_HEX(SHA256(company_name)), 1, 8)) as company_name,
  src.* EXCEPT(company_name)
FROM `{source_table}` src
```

### 3. Pattern-Based Anonymization
```sql
-- Use CASE statements for specific company patterns
CREATE OR REPLACE TABLE `{target_table}` AS
SELECT 
  CASE 
    WHEN company_name LIKE '%Inc%' THEN CONCAT('Company_', ROW_NUMBER() OVER (ORDER BY company_name))
    WHEN company_name LIKE '%Corp%' THEN CONCAT('Corporation_', ROW_NUMBER() OVER (ORDER BY company_name))
    ELSE CONCAT('Entity_', ROW_NUMBER() OVER (ORDER BY company_name))
  END as company_name,
  src.* EXCEPT(company_name)
FROM `{source_table}` src
```

### 4. Multiple Column Anonymization
```sql
-- Anonymize multiple columns
CREATE OR REPLACE TABLE `{target_table}` AS
SELECT 
  CONCAT('Company_', ROW_NUMBER() OVER (ORDER BY company_name)) as company_name,
  CONCAT('Contact_', ROW_NUMBER() OVER (ORDER BY contact_name)) as contact_name,
  -- Keep financial data unchanged
  revenue,
  expenses,
  date
FROM `{source_table}` src
```

### 5. Conditional Anonymization
```sql
-- Only anonymize certain companies or data
CREATE OR REPLACE TABLE `{target_table}` AS
SELECT 
  CASE 
    WHEN revenue > 1000000 THEN CONCAT('LargeCompany_', ROW_NUMBER() OVER (ORDER BY revenue DESC))
    WHEN company_name IN ('SpecificCompany1', 'SpecificCompany2') THEN 'AnonymizedEntity'
    ELSE company_name  -- Keep small companies as-is
  END as company_name,
  src.* EXCEPT(company_name)
FROM `{source_table}` src
```

### 6. Direct Copy (No Anonymization)
```sql
-- For tables without sensitive data
CREATE OR REPLACE TABLE `{target_table}` AS
SELECT * FROM `{source_table}`
```

## Testing Your Anonymization Logic

1. **Manual Testing**: Replace parameters with actual values and test in BigQuery console
2. **Verify Anonymization**: Check that real company names don't appear in results
3. **Data Integrity**: Ensure record counts and financial totals match
4. **Performance**: Test with large datasets to ensure queries perform well

## Security Best Practices

- **Preserve Data Relationships**: Ensure the same company gets the same anonymous name across tables
- **Test Thoroughly**: Verify no real company names leak through edge cases
- **Document Approach**: Comment your SQL to explain the anonymization strategy
- **Consider Performance**: Some anonymization approaches may be slower than others 