# Contractor Development Environment Setup Tool

This repository contains a comprehensive automation tool for setting up isolated development environments for external contractors working on Google Cloud Platform projects. The tool handles GCP project creation, data anonymization, BigQuery table copying, service account management, and GitHub repository setup.

## Overview

When working with external contractors on sensitive financial data projects, you need to:
1. **Isolate environments** - Give contractors their own GCP project to prevent access to production
2. **Anonymize data** - Protect company identities while providing real financial data for development
3. **Automate setup** - Reduce manual work and ensure consistent environments
4. **Enable collaboration** - Provide contractors with everything they need to develop and test code
5. **Easy cleanup** - Remove environments when projects are complete

This tool automates the entire process programmatically.

## What It Does

### For Each Contractor, the Tool:

1. **Creates a new GCP project** with billing enabled
2. **Sets up service accounts** with appropriate permissions
3. **Copies BigQuery tables** from production with anonymized company names
4. **Creates a private GitHub repository** with:
   - Service account credentials
   - Updated code with correct project references
   - Complete setup instructions
   - Requirements and dependencies
5. **Generates detailed instructions** for the contractor
6. **Adds the contractor** as a collaborator on the repository

### Security & Privacy Features:

- **Data anonymization** using canonical company name lookup tables
- **Isolated GCP projects** - contractors can't access production
- **Time-limited access** - easy to clean up when done
- **Private repositories** - code and credentials are not public
- **Minimal permissions** - contractors only get what they need

## Files in This Repository

### Core Tools
- **`files_and_scripts/setup_contractor_env.py`** - Main automation script that sets up everything
- **`files_and_scripts/cleanup_contractor_env.py`** - Removes contractor environments when projects are done
- **`config/contractor_config_simple_template.yaml`** - Configuration template for each contractor

### Setup & Dependencies
- **`files_and_scripts/setup_prerequisites.sh`** - Installs required tools (gcloud, gh CLI, Python packages)
- **`files_and_scripts/setup_master_config.py`** - Interactive setup for master configuration
- **`files_and_scripts/example_setup.sh`** - Complete example workflow script
- **`requirements.txt`** - Python dependencies for the setup tools

### Configuration
- **`config/master_config.yaml`** - Your authentication IDs and organizational defaults (created by setup)
- **`config/contractor_config_simple_template.yaml`** - Template for contractor-specific configs

### Reference Files
- **`initial_reference/example_of_type_of_script_contractor_would_edit.py`** - Example script that gets copied to contractor repos
- **`initial_reference/example_data_transfer_from_prod_to_dev.sql`** - Example of data transfer with anonymization
- **`initial_reference/canonical_company_names/`** - Directory containing company name anonymization data

## Quick Start

### 1. Initial Setup (One Time)

```bash
# Install prerequisites
chmod +x files_and_scripts/setup_prerequisites.sh
./files_and_scripts/setup_prerequisites.sh

# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_MAIN_PROJECT_ID

# Authenticate with GitHub
gh auth login

# Set up your master configuration (interactive)
python3 files_and_scripts/setup_master_config.py
```

### 2. Set Up a Contractor Environment

```bash
# Copy the simple contractor template
cp config/contractor_config_simple_template.yaml config/john_smith.yaml

# Edit the contractor file (only need contractor-specific info!)
# - contractor_name: "John Smith"
# - github_username: "johnsmith123"

# Run the setup (dry run first to see what will happen)
python3 files_and_scripts/setup_contractor_env.py --config config/john_smith.yaml --dry-run

# Actually create the environment
python3 files_and_scripts/setup_contractor_env.py --config config/john_smith.yaml
```

### 3. When Project is Complete

```bash
# List all contractor projects
python3 files_and_scripts/cleanup_contractor_env.py --list-projects

# Clean up a specific contractor environment
python3 files_and_scripts/cleanup_contractor_env.py --project-id contractor-john-smith-dev-2024
```

## How It Works

### Data Flow

```
Production Environment (assembled-wh)
    ↓
[Copy Tables with Anonymization]
    ↓
Contractor Development Environment
    ↓
[GitHub Repository with Code & Credentials]
    ↓
Contractor Development Work
```

### Anonymization Process

1. **Canonical Names Table**: Your `canonical_company_names_sa` table maps real company names to anonymized public names
2. **Table Copying**: When copying tables, the tool joins with the canonical names table to replace real company names with anonymized versions
3. **Data Integrity**: All financial data remains real and accurate, only company identities are protected

### Example Anonymization

```sql
-- Original production data
company_name: "Acme Corp Private Ltd"
revenue: 5000000

-- Anonymized contractor data  
company_name: "Company_A"
revenue: 5000000
```

## Configuration Options

All configuration is now explicitly defined in the YAML file. Copy `contractor_config_template.yaml` and modify the values as needed.

### Required Fields (Contractor-Specific)
- `contractor_name`: Full name of the contractor
- `github_username`: Their GitHub username for repository access
- `project_id`: Unique GCP project ID (must be globally unique)
- `project_name`: Human-readable project name
- `billing_account_id`: Your GCP billing account ID

### Required Fields (Organization Defaults)
- `source_project`: Source GCP project to copy data from
- `source_dataset`: Source BigQuery dataset
- `target_dataset`: Target BigQuery dataset in contractor project
- `tables_to_copy`: List of tables to copy from production

### Example Configuration

```yaml
# Contractor-specific information
contractor_name: "John Smith"
github_username: "johnsmith123"
project_id: "contractor-john-smith-dev-2024"
project_name: "Contractor John Smith Development Environment"
billing_account_id: "01234567-89ABCD-EFGHIJ"

# Your organization defaults
source_project: "assembled-wh"
source_dataset: "warehouse"
target_dataset: "warehouse"
tables_to_copy:
  - "ifms"
  - "ifms_consolidated"
  - "ifms_wa"
  - "ifms_consolidated_ttm_avg_data"
```

### Customizing for Different Contractors

You can easily customize the configuration for specific contractors:

```yaml
# For a contractor who needs additional tables
tables_to_copy:
  - "ifms"
  - "ifms_consolidated"
  - "ifms_wa"
  - "ifms_consolidated_ttm_avg_data"
  - "special_analysis_table"

# For a contractor working with a different source project
source_project: "my-other-project"
source_dataset: "analytics"
```

## What Contractors Receive

Each contractor gets:

1. **Private GitHub Repository** containing:
   - Updated Python script with correct project references
   - Service account JSON key file
   - Complete README with setup instructions
   - requirements.txt with all dependencies

2. **GCP Project Access** with:
   - BigQuery dataset with anonymized production data
   - Service account with necessary permissions
   - Ability to create Cloud Run services
   - Access to Secret Manager

3. **Detailed Instructions** including:
   - How to set up their local environment
   - How to run and test the code
   - What they have access to
   - Data privacy guidelines
   - Project timeline and deliverables

## Security Considerations

### What's Protected
- **Company identities** are anonymized in all data
- **Production environment** is completely isolated
- **Access is time-limited** and easy to revoke
- **Private repositories** keep code and credentials secure

### What Contractors Can Access
- Only the development GCP project you create for them
- Only the anonymized data you copy over
- Only the specific GitHub repository for their project

### Best Practices
- **Review the canonical names table** to ensure anonymization is complete
- **Set project deadlines** and clean up environments promptly
- **Monitor usage** through GCP billing and usage reports
- **Use private repositories** for all contractor work

## Troubleshooting

### Common Issues

1. **"Project ID already exists"**
   - Project IDs must be globally unique across all of Google Cloud
   - Try adding a timestamp or random suffix

2. **"Billing account not found"**
   - Run `gcloud billing accounts list` to get the correct ID
   - Ensure you have billing admin permissions

3. **"GitHub CLI not authenticated"**
   - Run `gh auth login` and follow the prompts
   - Ensure you have repository creation permissions

4. **"BigQuery table not found"**
   - Verify the source project and dataset names
   - Ensure you have BigQuery admin permissions on the source project

### Getting Help

- Check the log files created during setup (named `contractor_setup_TIMESTAMP.log`)
- Use the `--dry-run` flag to see what would happen without making changes
- Verify all prerequisites are installed with `./setup_prerequisites.sh`

## Cost Management

- Each contractor environment will incur GCP costs (BigQuery storage, compute, etc.)
- Monitor costs through the GCP billing console
- Clean up environments promptly when projects are complete
- Consider setting up billing alerts for contractor projects

## Example Workflow

## Virtual Environment Setup

```bash
# Create a virtual environment
python -m venv venv

# Activate it
source venv/bin/activate
pip install -r requirements.txt
```

- May 28, 2025 1:54 PM done


```bash
# 1. One-time setup
./files_and_scripts/setup_prerequisites.sh
gcloud auth login
gh auth login



# 2. For each new contractor
cp config/contractor_config_simple_template.yaml config/alice.yaml
# Edit config/alice.yaml with her details
python3 files_and_scripts/setup_contractor_env.py --config config/alice.yaml

# 3. Contractor works in their environment
# (They receive GitHub repo invitation and instructions)

# 4. When project is complete
python3 files_and_scripts/cleanup_contractor_env.py --project-id contractor-alice-dev-2024
```

This tool transforms a manual, error-prone process into a reliable, automated workflow that scales as you work with more contractors while maintaining security and data privacy.

## Virtual Environment Setup

```bash
# Create a virtual environment
python -m venv venv

# Activate it
source venv/bin/activate
pip install -r requirements.txt
```

