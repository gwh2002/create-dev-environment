#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Risk Rating Calculator for Bellaventure
This script calculates risk ratings based on financial metrics from BigQuery data.
"""
import os
import logging
import json
import pandas as pd
import numpy as np
from flask import Flask, jsonify
from google.cloud import bigquery, secretmanager
from google.oauth2 import service_account
import pandas_gbq
import inspect
import re

RUN_MODE = os.environ.get("RUN_MODE", "server")  # Options: 'server' or 'direct'

# ----- Risk Threshold Definitions -----
# Define risk thresholds (metric_name, threshold, operator, risk_points, [compare_to_other_metric])
RISK_FLAG_DEFINITIONS = {
    'negative_operating_income_ttm_flag': ('ttm_operating_income', 0, '<', 1),
    'negative_retained_earnings_flag': ('period_value_cumulative_retained_earnings', 0, '<', 1),
    'modified_quick_ratio_less_one_flag': ('modified_quick_ratio', 1, '<', 1),
    'yoy_revenue_decline_flag': ('yoy_revenue_change', 0, '<', 1),
    'ab_debt_exceeds_contributed_capital_flag': ('period_value_ab_loan_balance', 'period_value_contributed_capital', '>', 1, True),
    'inventory_turnover_below_2_flag': ('inventory_turns_ttm', 2, '<', 1),
    'ab_loc_25_percent_of_revenue_flag': ('ab_line_of_credit_as_percent_of_ttm_revenue', 0.25, '>', 1),
    'revenue_below_10_million_flag': ('ttm_revenue', 10000, '<', 1),
    'less_than_1_year_of_runway_flag': ('years_of_runway', (0, 1), 'between', 1),
}

# ----- BigQuery Configuration -----
CLOUD_RUN_PROJECT = "915401990209"  # assembled-wh project number
BIGQUERY_PROJECT = "assembled-wh"
BIGQUERY_DATASET = "warehouse"

SOURCE_DATA_TABLE_NAME = "ifms_consolidated_ttm_avg_data"
RISK_RATING_OUTPUT_TABLE_NAME = "risk_rating_all_time_historical"

# ----- Derived Metric Definitions -----
# These definitions specify how derived metrics are calculated
DERIVED_METRICS = {
# Convert TTM averages to TTM totals
    "ttm_revenue": {
        "formula": lambda df: df['ttm_avg_revenue'] * 12
    },
    "ttm_operating_income": {
        "formula": lambda df: df['ttm_avg_operating_income'] * 12
    },
    "ttm_costs_of_goods_sold": {
        "formula": lambda df: df['ttm_avg_costs_of_goods_sold'] * 12
    },
    "pttm_revenue": {
        "formula": lambda df: df['pttm_avg_revenue'] * 12
    },
    "yoy_revenue_change": {
        "formula": lambda df: df['ttm_avg_revenue'] / df['pttm_avg_revenue'] - 1
    },
    "years_of_runway": {
        "formula": lambda df: np.where(
            df['period_value_cash'] / (df['ttm_avg_operating_income'] * 12) > 0,
            -1,
            -(df['period_value_cash'] / (df['ttm_avg_operating_income'] * 12))
        )
    },
    # Business-specific derived metrics
    "ab_line_of_credit_as_percent_of_ttm_revenue": {
        "formula": lambda df: df['period_value_ab_loan_balance'] / (df['ttm_avg_revenue'] * 12)
    },
    "inventory_turns_ttm": {
        "formula": lambda df: df['ttm_avg_costs_of_goods_sold'] * 12 / df['ttm_avg_inventory']
    },
    
    # Modified quick ratio: (Cash + AR) / (AP + Credit Cards)
    "modified_quick_ratio": {
        "formula": lambda df: (
            df['period_value_cash'] + df['period_value_accounts_receivable']
        ) / np.where(
            df['period_value_accounts_payable'] + df['period_value_credit_cards'] != 0,
            df['period_value_accounts_payable'] + df['period_value_credit_cards'],
            np.nan
        )
    }
}

# ----- Setup Logging -----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ----- Flask App -----
app = Flask(__name__)

@app.route('/health')
def health_check():
    """Health check endpoint for the service"""
    return jsonify({"status": "healthy"}), 200

@app.route('/process', methods=['POST'])
def trigger_processing():
    """Endpoint to trigger the risk rating calculation process"""
    try:
        process_risk_ratings()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# ----- Secret Manager Functions -----
def access_secret_version(secret_id, version_id="latest"):
    """
    Access a secret from Secret Manager or local file.
    
    Args:
        secret_id (str): The ID of the secret to access.
        version_id (str): The version of the secret to access. Defaults to "latest".
        
    Returns:
        str: The secret value as a string.
        
    Raises:
        Exception: If the secret cannot be accessed.
    """
    # First try to load from local file for development
    local_secret_path = "service-account-key.json"
    if os.path.exists(local_secret_path):
        try:
            with open(local_secret_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Failed to load local secret: {str(e)}")
    
    # Fall back to Secret Manager
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{CLOUD_RUN_PROJECT}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Error accessing secret: {str(e)}")
        raise

def get_bigquery_credentials():
    """
    Get BigQuery credentials from Secret Manager.
    
    Returns:
        Credentials: The BigQuery credentials.
        
    Raises:
        Exception: If the credentials cannot be loaded.
    """
    try:
        # Access the secret containing the service account key
        secret_value = access_secret_version("bellaventure_service_account_json")
        
        # Parse the JSON string into a dictionary
        service_account_info = json.loads(secret_value)
        
        # Create credentials from the service account info
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        
        logger.info("Successfully loaded credentials from Secret Manager")
        return credentials
    except Exception as e:
        logger.error(f"Failed to load credentials from Secret Manager: {str(e)}")
        raise

# ----- Data Processing Functions - main table -----
def fetch_financial_data(client):
    """
    First big query to BigQuery to get the individual metrics per company.
    
    Args:
        client (bigquery.Client): The BigQuery client.
        
    Returns:
        DataFrame: The fetched data.
        
    Raises:
        Exception: If the query fails.
    """
    logger.info(f"Fetching data from {SOURCE_DATA_TABLE_NAME}")
    
    # BigQuery SQL Query
    table_path = f"`{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{SOURCE_DATA_TABLE_NAME}`"
    query = f"""
    SELECT
        company_name,
        time_period,
        metric_name,
        period_value,
        ttm_avg,
        pttm_avg
    FROM
        {table_path}
    """

    # Query parameters
    job_config = bigquery.QueryJobConfig()
    
    # Execute query with proper error handling
    try:
        logger.info("Executing BigQuery query...")
        logger.info(f"Using table path: {table_path}")
        logger.info(f"Full query: {query}")
        
        # Start the query
        query_job = client.query(query, job_config=job_config)
        
        # Set a timeout for the query
        import concurrent.futures
        import time
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Define a function to check query status
            def check_query_status():
                start_time = time.time()
                while True:
                    elapsed = time.time() - start_time
                    if elapsed > 10:  # Log status every 10 seconds
                        logger.info(f"Query still running after {elapsed:.1f} seconds. State: {query_job.state}")
                        start_time = time.time()
                    if query_job.done():
                        break
                    time.sleep(1)
                return query_job
            
            # Submit the check_query_status function to the executor
            future = executor.submit(check_query_status)
            
            try:
                # Wait for the query to complete, with a timeout
                job = future.result(timeout=300)  # 5 minute timeout
                
                # Check for errors
                if job.errors:
                    for error in job.errors:
                        logger.error(f"Query error: {error}")
                    raise ValueError(f"Query execution failed: {job.errors}")
                
                # Get results
                logger.info(f"Query completed successfully. State: {job.state}")
                df = job.to_dataframe()
                
            except concurrent.futures.TimeoutError:
                logger.error("Query execution timed out after 5 minutes")
                # Try to cancel the query
                query_job.cancel()
                raise TimeoutError("BigQuery query timed out after 5 minutes")
        
        # Check if we got any results
        if df.empty:
            logger.warning(f"Query returned no results. Check the query: {query}")
        else:
            logger.info(f"Query executed successfully. Retrieved {len(df)} rows.")
        
        # Standardize column names
        df.columns = df.columns.str.lower().str.replace(' ', '_')
        
        return df
    except Exception as e:
        # Handle different types of errors
        error_msg = str(e)
        if "Syntax error" in error_msg:
            logger.error(f"SQL syntax error in query: {error_msg}")
            # Log the query with parameters for debugging
            logger.error(f"Query with syntax error: {query}")
            logger.error(f"Parameters: {job_config}")
        elif "Not found" in error_msg:
            logger.error(f"Table or dataset not found: {error_msg}")
            logger.error(f"Verify that {table_path} exists")
        elif "Permission denied" in error_msg:
            logger.error(f"Permission denied: {error_msg}")
            logger.error("Verify that the service account has proper permissions")
        else:
            logger.error(f"Failed to execute BigQuery query: {error_msg}", exc_info=True)
        
        # Raise a more informative exception
        raise ValueError(f"BigQuery query failed: {error_msg}")
    finally:
        logger.info("Query function completed")

def pivot_financial_data(df):
    """
    Pivot the financial data for easier analysis.
    
    Args:
        df (DataFrame): The raw financial data.
        
    Returns:
        DataFrame: The pivoted data.
        
    Raises:
        Exception: If the pivot operation fails.
    """
    logger.info("Pivoting data...")
    try:
        pivoted_df = df.pivot_table(
            index=['company_name', 'time_period'],
            columns='metric_name',
            values=['period_value', 'ttm_avg', 'pttm_avg'],
            aggfunc='max'
        ).reset_index()
        
        # Convert the MultiIndex to regular column names and standardize
        pivoted_df.columns = ['_'.join([str(col).lower() for col in col_tuple]).strip('_') 
                             for col_tuple in pivoted_df.columns.values]
        pivoted_df.columns = pivoted_df.columns.str.replace(' ', '_')
        
        logger.info(f"Pivoted DataFrame columns: {pivoted_df.columns.tolist()}")
        
        # Nullify zeros in value columns - only for columns that exist
        columns_to_nullify = [col for col in pivoted_df.columns 
                             if any(col.startswith(substr) for substr in 
                                   ['period_value_', 'ttm_avg_', 'pttm_avg_'])]
        
        logger.info(f"Columns to nullify: {columns_to_nullify}")
        
        # Only process columns that exist in the DataFrame
        existing_columns = [col for col in columns_to_nullify if col in pivoted_df.columns]
        
        logger.info(f"Existing columns to process: {existing_columns}")
        
        # Process each column individually to avoid any potential DataFrame structure issues
        for col in existing_columns:
            logger.info(f"Processing column: {col}")
            pivoted_df[col] = pivoted_df[col].replace(0, np.nan)
        
        logger.info("Data pivoted successfully.")
        return pivoted_df
    except Exception as e:
        logger.error("Failed to pivot DataFrame.", exc_info=True)
        raise

def calculate_derived_metrics(df):
    """
    Calculate derived financial metrics defined 
    in the dictionary in the config section of this file.
    
    Args:
        df (DataFrame): The pivoted financial data.
        
    Returns:
        DataFrame: The data with derived metrics added.
    """
    logger.info("Calculating derived metrics...")
    
    # Dynamically include all derived metrics and their dependencies
    derived_metrics = list(DERIVED_METRICS.keys())
    for metric_info in DERIVED_METRICS.values():
        # Extract all column names used in the formulas
        formula_str = str(metric_info['formula'])
        for col in df.columns:
            if col in formula_str and col not in derived_metrics:
                derived_metrics.append(col)
    
    # Create a dictionary to store all new columns
    new_columns = {}
    
    # Calculate all derived metrics at once
    for metric_name in derived_metrics:
        try:
            new_columns[metric_name] = DERIVED_METRICS[metric_name]["formula"](df)
            logger.info(f"Calculated {metric_name} successfully.")
        except KeyError as e:
            logger.error(f"Missing column for {metric_name}: {e}")
            raise
    
    # Add all new columns at once using pd.concat
    new_df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
    
    logger.info("Derived metrics calculated successfully.")
    return new_df

def get_metrics_from_risk_flag_definitions(df):
    """
    Extract all metrics referenced in RISK_FLAG_DEFINITIONS
    so that we can output them in the final table.
    
    Args:
        df (DataFrame): The dataframe containing the metrics.
        
    Returns:
        tuple: (risk_flag_names, metrics_from_risk_flags)
    """
    risk_flag_names = list(RISK_FLAG_DEFINITIONS.keys())
    metrics_from_risk_flags = set()
    
    for flag_def in RISK_FLAG_DEFINITIONS.values():
        metrics_from_risk_flags.add(flag_def[0])  # First element is always a metric
        if isinstance(flag_def[1], str) and flag_def[1] in df.columns:
            # Second element is a metric name if it's a string and in our dataframe
            metrics_from_risk_flags.add(flag_def[1])
    
    return risk_flag_names, metrics_from_risk_flags

def confirm_availability_of_metrics_used_for_risk_ratings(df):
    """
    Error check to validate all metrics referenced 
    in RISK_FLAG_DEFINITIONS dictionary in config section
    exist in the dataframe. This is bout aligning the
    naming conventions between this file and the BQ table
    we fetch in fetch_financial_data().
    
    Args:
        df (DataFrame): The dataframe containing the metrics.
        
    Raises:
        ValueError: If any metrics referenced in RISK_FLAG_DEFINITIONS don't exist in the dataframe.
    """
    undefined_metrics = []
    
    for flag_name, flag_def in RISK_FLAG_DEFINITIONS.items():
        # First element is always a metric
        metric_name = flag_def[0]
        if metric_name not in df.columns:
            undefined_metrics.append(f"'{metric_name}' referenced in '{flag_name}'")
        
        # Second element might be a metric or a threshold value
        if isinstance(flag_def[1], str):
            metric_name = flag_def[1]
            if metric_name not in df.columns:
                undefined_metrics.append(f"'{metric_name}' referenced in '{flag_name}'")
    
    if undefined_metrics:
        error_msg = "RISK_FLAG_DEFINITIONS references undefined metrics: " + ", ".join(undefined_metrics)
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("All metrics referenced in RISK_FLAG_DEFINITIONS are valid.")
    
    return True

def calculate_risk_ratings(df):
    """
    Calculate risk flags and ratings based on defined thresholds.
    
    Args:
        df (DataFrame): The financial data with derived metrics.
        
    Returns:
        DataFrame: The data with risk flags and ratings added.
    """
    logger.info("Calculating risk flags and ratings...")
    logger.info(f"Columns before risk calculation: {df.columns.tolist()}")
    
    # Create a dictionary to store all new columns
    new_columns = {
        'risk_flags': 0,
        'risk_rating': 0
    }
    
    # Initialize all risk flag columns
    for metric in RISK_FLAG_DEFINITIONS.keys():
        new_columns[metric] = 0

    # Create a new DataFrame with all columns at once
    df = pd.concat([df, pd.DataFrame(new_columns, index=df.index)], axis=1)
    logger.info(f"Columns after adding new columns: {df.columns.tolist()}")
    
    # Apply thresholds and calculate risk flags
    for metric, criteria in RISK_FLAG_DEFINITIONS.items():
        metric_name, threshold, operator, risk_points, *optional = criteria
        compare = optional[0] if len(optional) > 0 else False
        
        # Determine required metrics for this flag
        required_metrics = [metric_name]
        if compare:
            required_metrics.append(threshold)
        
        # Mark rows with missing data
        missing_metrics = df[required_metrics].isnull().any(axis=1)
        df.loc[missing_metrics, metric] = -1
        
        # Apply threshold logic
        valid_data = ~missing_metrics
        if compare:
            if operator == '<':
                df.loc[valid_data & (df[metric_name] < df[threshold]), metric] = 1
            elif operator == '>':
                df.loc[valid_data & (df[metric_name] > df[threshold]), metric] = 1
            elif operator == 'between':
                lower, upper = threshold
                df.loc[valid_data & (df[metric_name] >= lower) & (df[metric_name] < upper), metric] = 1
        else:
            if operator == '<':
                df.loc[valid_data & (df[metric_name] < threshold), metric] = 1
            elif operator == '>':
                df.loc[valid_data & (df[metric_name] > threshold), metric] = 1
            elif operator == 'between':
                lower, upper = threshold
                df.loc[valid_data & (df[metric_name] >= lower) & (df[metric_name] < upper), metric] = 1
    
    # Calculate risk rating and null flags in one go
    risk_flag_columns = list(RISK_FLAG_DEFINITIONS.keys())
    df['risk_rating'] = df[risk_flag_columns].apply(
        lambda row: round(row[row != -1].mean() * 10, 1) if any(row != -1) else -1, axis=1)
    df['num_flags_with_missing_underlying_data'] = df[risk_flag_columns].apply(
        lambda row: sum(val == -1 for val in row), axis=1)
    
    return df

def write_risk_rating_output_to_bigquery(df, credentials):
    """
    Write the risk rating, risk flags, and underlying metrics to BigQuery.
    
    Args:
        df (DataFrame): The data to write.
        credentials: The BigQuery credentials.
        
    Raises:
        Exception: If the write operation fails.
    """
    logger.info("Writing data to BigQuery...")
    try:
        # Pass the dataframe to get_metrics_from_risk_flag_definitions
        risk_flag_names, metrics_from_risk_flags = get_metrics_from_risk_flag_definitions(df)
                
        # Extract metrics from DERIVED_METRICS
        derived_metric_names = list(DERIVED_METRICS.keys())
        
        # Combine all metrics
        numeric_columns = ['risk_rating', 'num_flags_with_missing_underlying_data']
        numeric_columns.extend(risk_flag_names)  # Add all risk flags
        #present in numeric_columns
        numeric_columns.extend(metrics_from_risk_flags)  # Add metrics used in risk flag definitions
        #present in numeric_columns
        numeric_columns.extend(derived_metric_names)  # Add derived metrics
        
        # Remove duplicates while preserving order
        logger.info(f"Metrics from risk flags: {metrics_from_risk_flags}")
        logger.info(f"All numeric columns before deduplication: {numeric_columns}")
        logger.info(f"DataFrame columns: {df.columns.tolist()}")
        unique_numeric_columns = []
        for col in numeric_columns:
            if col not in unique_numeric_columns and col in df.columns:
                unique_numeric_columns.append(col)
        #this is where cumulative retained earnings is getting dropped
        logger.info(f"Processing {len(unique_numeric_columns)} numeric columns")
        
        # Explicitly convert all numeric columns to float64
        for col in unique_numeric_columns:
            # Replace empty strings with NaN first if needed
            if df[col].dtype == 'object':
                df[col] = df[col].replace('', np.nan)
            df[col] = pd.to_numeric(df[col], errors='coerce')
                
        # Define explicit schema to help pandas_gbq
        schema = [
            {'name': 'company_name', 'type': 'STRING'},
            {'name': 'time_period', 'type': 'TIMESTAMP'}
        ]
        
        # Add schema for all columns based on type
        for col in df.columns:
            if col in ['company_name', 'time_period']:
                continue  # Already added
            elif col in risk_flag_names or col == 'num_flags_with_missing_underlying_data':
                schema.append({'name': col, 'type': 'INTEGER'})
            elif col in unique_numeric_columns:
                schema.append({'name': col, 'type': 'FLOAT'})
        
        # Log column types for debugging
        logger.info(f"Column dtypes before BigQuery upload: {df.dtypes}")
        
        # Construct the full table path
        table_path = f"{BIGQUERY_DATASET}.{RISK_RATING_OUTPUT_TABLE_NAME}"
        logger.info(f"Writing data to table: {table_path}")
        
        pandas_gbq.to_gbq(
            df,
            table_path,
            project_id=BIGQUERY_PROJECT,
            if_exists='replace',
            credentials=credentials,
            table_schema=schema
        )
        logger.info("Data written to BigQuery successfully.")
    except Exception as e:
        logger.error(f"Failed to write data to BigQuery: {str(e)}", exc_info=True)
        raise

def write_current_risk_ratings(df, credentials):
    """
    Write a second table to BigQuery with that
    1/ filters to most recent period for each company
    2/ creates columns aggregating the names of 
    a) flags that are 1 (flagged)
    b) flags that are -1 (missing data)
    
    Args:
        df (DataFrame): The data with risk ratings and flags.
        credentials: The BigQuery credentials.
    """
    logger.info("Writing current risk ratings to BigQuery...")
    try:
        # Get risk flag columns
        risk_flag_columns = [col for col in df.columns if col.endswith('_flag')]
        
        # Create a function to aggregate flags based on value
        def aggregate_flags(row, value):
            flags = []
            for col in risk_flag_columns:
                if row[col] == value:
                    # Remove '_flag' suffix and convert to canonical name using the same logic
                    # as in the original SQL
                    metric_name = col.replace('_flag', '')
                    flags.append(f"'{metric_name}'")
            return ', '.join(flags) if flags else ('no flags' if value == 1 else 'no missing data')
        
        # Create a copy of the dataframe for processing
        current_df = df.copy()
        
        # Add aggregated flag columns
        current_df['risk_flags_flagged'] = current_df.apply(lambda row: aggregate_flags(row, 1), axis=1)
        current_df['risk_flags_flagged_num'] = current_df[risk_flag_columns].apply(
            lambda row: sum(val == 1 for val in row), axis=1)
        current_df['risk_flags_with_missing_underlying_data'] = current_df.apply(
            lambda row: aggregate_flags(row, -1), axis=1)
        
        # Get the most recent time period for each company
        current_df['time_period'] = pd.to_datetime(current_df['time_period'])
        latest_periods = current_df.groupby('company_name')['time_period'].transform('max')
        current_df = current_df[current_df['time_period'] == latest_periods]
        
        # Define column order and schema together
        column_schema = [
            ('company_name', 'STRING'),
            ('time_period', 'TIMESTAMP'),
            ('risk_rating', 'FLOAT'),
            ('num_flags_with_missing_underlying_data', 'INTEGER'),
            ('risk_flags_with_missing_underlying_data', 'STRING'),
            ('risk_flags_flagged', 'STRING'),
            ('risk_flags_flagged_num', 'INTEGER')
        ]
        
        # Add risk flag columns to schema
        for col in risk_flag_columns:
            column_schema.append((col, 'INTEGER'))
            
        # Add remaining numeric columns
        remaining_columns = [col for col in current_df.columns 
                           if col not in dict(column_schema) and 
                           col not in risk_flag_columns]
        for col in remaining_columns:
            column_schema.append((col, 'FLOAT'))
        
        # Extract ordered columns and schema
        ordered_columns = [col for col, _ in column_schema]
        schema = [{'name': col, 'type': type_} for col, type_ in column_schema]
        
        # Reorder the DataFrame
        current_df = current_df[ordered_columns]
        
        # Write to BigQuery
        table_path = f"{BIGQUERY_DATASET}.risk_rating_current"
        logger.info(f"Writing current risk ratings to table: {table_path}")
        
        pandas_gbq.to_gbq(
            current_df,
            table_path,
            project_id=BIGQUERY_PROJECT,
            if_exists='replace',
            credentials=credentials,
            table_schema=schema
        )
        logger.info("Current risk ratings written to BigQuery successfully.")
        
    except Exception as e:
        logger.error(f"Failed to write current risk ratings to BigQuery: {str(e)}", exc_info=True)
        raise

def get_formula_dependencies(formula_str):
    """Extract column names from a formula string."""
    # Find all strings that look like df['column_name']
    matches = re.findall(r"df\['([^']+)'\]", formula_str)
    return matches

def prepare_output_data(df, risk_flag_columns):
    """
    Collect and order all the relevant columns
    for the final table. We've designed the code 
    so that update the RISK_FLAG_DEFINITIONS 
    config e.g. with new flags and metrics
    will cause the new metrics to automatically
    flow to the to the final output
    """
    logger.info("Preparing output data...")
    
    # Define the desired columns for output - start with metadata columns
    desired_column_order = [
        'company_name',
        'time_period',
        'risk_rating',
        'num_flags_with_missing_underlying_data'
    ]
    
    logger.info(f"Initial columns: {desired_column_order}")
    
    # Add all risk flag columns in a consistent order
    desired_column_order.extend(sorted(risk_flag_columns))
    logger.info(f"After adding risk flags: {desired_column_order}")
    
    # Add derived metrics and their dependencies
    derived_metrics = list(DERIVED_METRICS.keys())
    dependencies = []
    for metric_info in DERIVED_METRICS.values():
        # Get the source code of the lambda function
        formula_str = inspect.getsource(metric_info['formula'])
        # Extract dependencies
        deps = get_formula_dependencies(formula_str)
        for dep in deps:
            if dep in df.columns and dep not in dependencies and dep not in derived_metrics:
                dependencies.append(dep)
    
    # Add both derived metrics and their dependencies
    desired_column_order.extend(derived_metrics)
    desired_column_order.extend(dependencies)
    
    logger.info(f"After adding derived metrics: {desired_column_order}")
    
    # Add metrics from risk flags
    risk_flag_names, metrics_from_risk_flags = get_metrics_from_risk_flag_definitions(df)
    for metric in metrics_from_risk_flags:
        if metric not in desired_column_order:
            desired_column_order.append(metric)
    
    logger.info(f"After adding risk flag metrics: {desired_column_order}")
    logger.info(f"Is period_value_cumulative_retained_earnings in desired columns? {('period_value_cumulative_retained_earnings' in desired_column_order)}")
    logger.info(f"Is period_value_cumulative_retained_earnings in df columns? {('period_value_cumulative_retained_earnings' in df.columns)}")
    
    # Select and reorder columns
    output_df = df[desired_column_order].copy()
    
    # Data type conversions
    output_df['company_name'] = output_df['company_name'].astype('string')
    output_df['time_period'] = pd.to_datetime(output_df['time_period'], errors='coerce')
    
    # Convert flag columns to integers explicitly
    flag_columns = [col for col in output_df.columns if col.endswith('_flag')]
    for col in flag_columns:
        output_df[col] = output_df[col].astype('int32')
    
    # Convert numerical columns to float64 (ensure we're handling empty strings properly)
    columns_to_convert = derived_metrics
    columns_to_convert.extend(['risk_rating', 'num_flags_with_missing_underlying_data'])
    
    for column in columns_to_convert:
        # Replace empty strings with NaN
        if column in output_df.columns:
            if output_df[column].dtype == 'object':
                output_df[column] = output_df[column].replace('', np.nan)
            output_df[column] = pd.to_numeric(output_df[column], errors='coerce')
    
    # Handle NaN values
    date_cols = ['time_period']
    string_cols = ['company_name']
    numeric_cols = [col for col in output_df.columns if col not in date_cols and col not in string_cols]
    
    # Fill NaN values appropriately by column type
    output_df[date_cols] = output_df[date_cols].fillna(pd.NaT)
    output_df[string_cols] = output_df[string_cols].fillna("")
    # For numeric columns, fill with None which will be translated to NULL in BigQuery
    for col in numeric_cols:
        output_df[col] = output_df[col].where(pd.notnull(output_df[col]), None)
    
    # Log column types for debugging
    logger.info(f"Column dtypes after preparation: {output_df.dtypes}")
    
    return output_df

def process_risk_ratings():
    """
    Invokes all the other functions in this file
    in the correct order.
    """
    logger.info("Starting risk rating calculation process...")
    
    # Set up environment
    os.environ["GOOGLE_CLOUD_PROJECT"] = BIGQUERY_PROJECT
    logger.info(f"Using BigQuery Project: {os.environ['GOOGLE_CLOUD_PROJECT']}")
    
    # Get credentials and create BigQuery client
    bq_credentials = get_bigquery_credentials()
    try:
        client = bigquery.Client(
            project=os.environ["GOOGLE_CLOUD_PROJECT"], 
            credentials=bq_credentials
        )
    except Exception as e:
        logger.error("Failed to create BigQuery client.", exc_info=True)
        raise
    
    # Process data
    df = fetch_financial_data(client)
    # df.to_csv('df.csv', index=False)

    pivoted_df = pivot_financial_data(df)
    # pivoted_df.to_csv('pivoted_df.csv', index=False)

    derived_df = calculate_derived_metrics(pivoted_df)
    # derived_df.to_csv('derived_df.csv', index=False)

    
    # Validate that all metrics referenced in RISK_FLAG_DEFINITIONS exist
    confirm_availability_of_metrics_used_for_risk_ratings(derived_df)
    
    # Calculate risk ratings
    risk_df = calculate_risk_ratings(derived_df)
    # risk_df.to_csv('risk_df.csv', index=False)

    
    # Get each risk flag column for output preparation
    risk_flag_columns = [col for col in risk_df.columns if col.endswith('_flag')]
    
    # Prepare and write output
    output_df = prepare_output_data(risk_df, risk_flag_columns)
    # output_df.to_csv('output_df.csv', index=False)
    write_risk_rating_output_to_bigquery(output_df, bq_credentials)
    write_current_risk_ratings(output_df, bq_credentials)
    
    logger.info("Risk rating calculation completed successfully.")

# ----- Main Execution -----
if __name__ == "__main__":
    logger.info("Script started.")
    
    if RUN_MODE.lower() == "server":
        # For Cloud Run or local server testing
        port = int(os.environ.get("PORT", 8080))
        app.run(host='0.0.0.0', port=port)
    else:
        # Direct execution for local testing
        process_risk_ratings()

