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
- **`config/contractor_config.yaml`** - Configuration template for each contractor

### Setup & Dependencies
- **`files_and_scripts/setup_prerequisites.sh`** - Installs required tools (gcloud, gh CLI, Python packages)
- **`files_and_scripts/setup_master_config.py`** - Interactive setup for master configuration
- **`files_and_scripts/example_setup.sh`** - Complete example workflow script
- **`requirements.txt`** - Python dependencies for the setup tools

### Configuration
- **`config/master_config.yaml`** - Your authentication IDs and organizational defaults (created by setup)
- **`config/contractor_config.yaml`** - Template for contractor-specific configs

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
# Copy the contractor config template and fill in the details
cp config/contractor_config.yaml config/new_contractor_config.yaml

# Edit the new file with contractor information:
# - contractor_name: "John Smith"
# - github_username: "johnsmith123"
# (All other organizational defaults come from master_config.yaml)

# The project ID will be auto-generated as: partner-john-smith-dev-2025
# (Based on project_id_prefix + contractor name + project_id_suffix from master_config.yaml)

# Run the setup (dry run first to see what will happen)
python3 files_and_scripts/setup_contractor_env.py --config config/new_contractor_config.yaml --dry-run

# Actually create the environment
python3 files_and_scripts/setup_contractor_env.py --config config/new_contractor_config.yaml
```

### 3. When Project is Complete

```bash
# List all contractor projects (with rich information from manifest)
python3 files_and_scripts/cleanup_contractor_env.py --list-projects

# Clean up by contractor name (intelligent matching)
python3 files_and_scripts/cleanup_contractor_env.py --contractor-name "Jim Smith" --dry-run

# Or clean up by project ID (if you know it)
python3 files_and_scripts/cleanup_contractor_env.py --project-id partner-alice-dev-2025
```

## Systematized Workflow & Intelligent Tracking

This tool now includes a sophisticated manifest-based tracking system that makes contractor environment management robust and systematic.

### Manifest-Based Tracking

The tool automatically maintains a `contractor_environments.yaml` manifest file that tracks:
- **Environment Details**: Project IDs, contractor names, creation dates
- **Resource Information**: GitHub repos, service accounts, tables copied
- **Status Tracking**: Active, completed, or deleted environments
- **Audit Trail**: Complete history of all contractor environments

### Intelligent Discovery & Cleanup

The cleanup system uses multiple discovery methods with graceful fallback:

1. **Primary Method**: Manifest-based lookup (fast, accurate, rich metadata)
2. **Fallback Method**: GCloud discovery (works even if manifest is missing)
3. **Interactive Selection**: When multiple matches or unclear naming

### Enhanced Commands

#### Environment Listing
```bash
# Rich listing with creation dates and status
python3 files_and_scripts/cleanup_contractor_env.py --list-projects

# Output example:
# Project ID                          Contractor           Created      Source    
# --------------------------------------------------------------------------------
# partner-jim-smith-dev-2025          Jim Smith            2025-05-29   manifest  
# partner-alice-jones-dev-2025        Alice Jones          2025-05-28   manifest
```

#### Smart Contractor Lookup
```bash
# Find environments by contractor name
python3 files_and_scripts/cleanup_contractor_env.py --contractor-name "Jim Smith"

# Partial name matching with interactive selection
python3 files_and_scripts/cleanup_contractor_env.py --contractor-name "John"
# Shows menu: "1. John Smith  2. John Doe  3. Johnny Cash"
```

#### Manifest Management
```bash
# View manifest statistics
python3 files_and_scripts/contractor_manifest.py --stats

# Search environments
python3 files_and_scripts/contractor_manifest.py --search "smith"

# List active environments only
python3 files_and_scripts/contractor_manifest.py --active

# Export to CSV for reporting
python3 files_and_scripts/contractor_manifest.py --export-csv contractor_report.csv
```

### Robust Edge Case Handling

The systematized approach handles various edge cases:

- **Manifest missing/corrupted** → Falls back to GCloud discovery
- **Resources manually renamed** → Shows user selection menu
- **Multiple contractors with similar names** → Interactive disambiguation
- **Partial cleanup failures** → Updates manifest with failure status
- **Legacy environments** → Can be added to manifest retroactively

### Complete Lifecycle Automation

```bash
# 1. Setup automatically adds to manifest
python3 files_and_scripts/setup_contractor_env.py --config config/contractor_config.yaml

# 2. Track and query environments
python3 files_and_scripts/contractor_manifest.py --list

# 3. Cleanup automatically updates manifest
python3 files_and_scripts/cleanup_contractor_env.py --contractor-name "Jim Smith"
```

### Benefits of the Systematized Approach

1. **Reliability**: No more manually tracking project IDs or guessing naming patterns
2. **Auditability**: Complete history of all contractor environments
3. **Team Collaboration**: Shared manifest file in git repo for team visibility
4. **Graceful Degradation**: Always works even if components fail
5. **Future-Proof**: Handles naming convention changes and organizational evolution

### Migration from Manual Tracking

If you have existing contractor environments, you can add them to the manifest:

```python
# Example: Add existing environment to manifest
from files_and_scripts.contractor_manifest import ContractorManifest, ContractorEnvironment
from datetime import datetime

manifest = ContractorManifest()
env = ContractorEnvironment(
    contractor_name="Existing Contractor",
    project_id="their-project-id",
    # ... other details
)
manifest.add_environment(env)
```

## Cost Management

- Each contractor environment will incur GCP costs (BigQuery storage, compute, etc.)
- Monitor costs through the GCP billing console
- Clean up environments promptly when projects are complete
- Consider setting up billing alerts for contractor projects
- Use the manifest reporting features to track environment lifecycle costs

## Complete Example Workflow

```bash
# 1. One-time setup
./files_and_scripts/setup_prerequisites.sh
gcloud auth login
gh auth login
python3 files_and_scripts/setup_master_config.py

# 2. For each new contractor
# Edit config/contractor_config.yaml with contractor details:
# - contractor_name: "John Smith"  
# - github_username: "johnsmith123"

# Preview what will be created
python3 files_and_scripts/setup_contractor_env.py --config config/contractor_config.yaml --dry-run

# Create the environment
python3 files_and_scripts/setup_contractor_env.py --config config/contractor_config.yaml

# 3. Track environments
python3 files_and_scripts/contractor_manifest.py --list

# 4. When project is complete
python3 files_and_scripts/cleanup_contractor_env.py --contractor-name "John Smith" --dry-run
python3 files_and_scripts/cleanup_contractor_env.py --contractor-name "John Smith"
```

This tool transforms a manual, error-prone process into a reliable, automated workflow that scales as you work with more contractors while maintaining security and data privacy through intelligent tracking and systematic management.

## Virtual Environment Setup

```bash
# Create a virtual environment
python -m venv venv

# Activate it
source venv/bin/activate
pip install -r requirements.txt
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
company_name: "Away Luggage"
revenue: 5000000

-- Anonymized contractor data  
company_name: "Eli Lilly"
revenue: 5000000
```

## Configuration Options

All configuration uses a simplified approach: contractor-specific information goes in the contractor config file, while organizational defaults come from `master_config.yaml`.

### Required Fields (In Contractor Config File)
- `contractor_name`: Full name of the contractor
- `github_username`: Their GitHub username for repository access

### Auto-Generated Values
- `project_id`: Automatically generated as `{prefix}-{contractor-name}-{suffix}` 
  - Example: "John Smith" becomes `partner-john-smith-dev-2025`
  - Based on `project_id_prefix` and `project_id_suffix` from master_config.yaml
- `project_name`: Auto-generated from template in master_config.yaml

### Optional Overrides (In Contractor Config File)
- `tables_to_copy`: Custom list of tables (uses defaults from master_config.yaml if not specified)
- `contractor_type`: If you've defined contractor types in master_config.yaml

### Organizational Defaults (From master_config.yaml)
- `billing_account_id`: Your GCP billing account ID
- `source_project`: Source GCP project to copy data from
- `source_dataset`: Source BigQuery dataset
- `target_dataset`: Target BigQuery dataset in contractor project
- `tables_to_copy`: Default list of tables to copy from production

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