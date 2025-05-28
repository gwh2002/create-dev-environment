#!/usr/bin/env python3
"""
Contractor Development Environment Setup Tool

This script automates the creation of isolated development environments for external contractors.
It handles GCP project creation, data anonymization, BigQuery table copying, service account setup,
and GitHub repository creation.
"""

import os
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'contractor_setup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# CONTRACTOR CONFIG CLASS
@dataclass
class ContractorConfig:
    """Configuration for a contractor environment"""
    """this is defined in the config.yaml file"""
    contractor_name: str
    github_username: str
    project_id: str
    project_name: str
    billing_account_id: str
    source_project: str
    source_dataset: str
    target_dataset: str
    tables_to_copy: List[str]

class ContractorEnvironmentSetup:
    """Main class for setting up contractor development environments"""
    
    def __init__(self, config: ContractorConfig):
        self.config = config
        self.temp_dir = None
        self.service_account_email = None
        self.service_account_key_path = None
        
    def setup_environment(self) -> Dict[str, str]:
        """
        Main method to set up the complete contractor environment
        
        Returns:
            Dict containing setup results and important information
        """
        logger.info(f"Starting environment setup for contractor: {self.config.contractor_name}")
        
        results = {
            "contractor_name": self.config.contractor_name,
            "project_id": self.config.project_id,
            "setup_timestamp": datetime.now().isoformat(),
            "status": "in_progress"
        }
        
        try:
            # Create temporary directory for operations
            self.temp_dir = tempfile.mkdtemp(prefix=f"contractor_setup_{self.config.contractor_name}_")
            logger.info(f"Created temporary directory: {self.temp_dir}")
            
            # Step 1: Create GCP Project
            logger.info("Step 1: Creating GCP Project")
            self._create_gcp_project()
            results["gcp_project_created"] = True
            
            # Step 2: Enable required APIs
            logger.info("Step 2: Enabling required APIs")
            self._enable_apis()
            results["apis_enabled"] = True
            
            # Step 3: Create service account
            logger.info("Step 3: Creating service account")
            self._create_service_account()
            results["service_account_email"] = self.service_account_email
            
            # Step 4: Copy and anonymize data
            logger.info("Step 4: Copying and anonymizing data")
            self._copy_and_anonymize_data()
            results["data_copied"] = True
            
            # Step 5: Create GitHub repository
            logger.info("Step 5: Creating GitHub repository")
            repo_url = self._create_github_repo()
            results["github_repo"] = repo_url
            
            # Step 6: Generate contractor instructions
            logger.info("Step 6: Generating contractor instructions")
            instructions_path = self._generate_contractor_instructions()
            results["instructions_path"] = instructions_path
            
            results["status"] = "completed"
            logger.info("Environment setup completed successfully!")
            
        except Exception as e:
            logger.error(f"Setup failed: {str(e)}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
            raise
        finally:
            # Cleanup temporary directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temporary directory")
        
        return results
    
    def _create_gcp_project(self):
        """Create a new GCP project"""
        logger.info(f"Creating GCP project: {self.config.project_id}")
        
        # Create project
        cmd = [
            "gcloud", "projects", "create", self.config.project_id,
            "--name", self.config.project_name,
            "--set-as-default"
        ]
        self._run_command(cmd, "Failed to create GCP project")
        
        # Link billing account
        if self.config.billing_account_id:
            cmd = [
                "gcloud", "billing", "projects", "link", self.config.project_id,
                "--billing-account", self.config.billing_account_id
            ]
            self._run_command(cmd, "Failed to link billing account")
        
        logger.info(f"GCP project {self.config.project_id} created successfully")
    
    def _enable_apis(self):
        """Enable required GCP APIs"""
        apis = [
            "bigquery.googleapis.com",
            "cloudbuild.googleapis.com",
            "run.googleapis.com",
            "secretmanager.googleapis.com",
            "iam.googleapis.com"
        ]
        
        for api in apis:
            logger.info(f"Enabling API: {api}")
            cmd = [
                "gcloud", "services", "enable", api,
                "--project", self.config.project_id
            ]
            self._run_command(cmd, f"Failed to enable API: {api}")
    
    def _create_service_account(self):
        """Create service account with necessary permissions"""
        sa_name = f"contractor-{self.config.contractor_name.lower().replace(' ', '-')}"
        sa_display_name = f"Service Account for {self.config.contractor_name}"
        
        # Create service account
        cmd = [
            "gcloud", "iam", "service-accounts", "create", sa_name,
            "--display-name", sa_display_name,
            "--project", self.config.project_id
        ]
        self._run_command(cmd, "Failed to create service account")
        
        self.service_account_email = f"{sa_name}@{self.config.project_id}.iam.gserviceaccount.com"
        
        # Grant necessary roles
        roles = [
            "roles/bigquery.admin",
            "roles/run.admin", 
            "roles/secretmanager.admin",
            "roles/storage.admin",
            "roles/cloudbuild.builds.editor"
        ]
        
        for role in roles:
            cmd = [
                "gcloud", "projects", "add-iam-policy-binding", self.config.project_id,
                "--member", f"serviceAccount:{self.service_account_email}",
                "--role", role
            ]
            self._run_command(cmd, f"Failed to grant role: {role}")
        
        # Create and download service account key
        self.service_account_key_path = os.path.join(self.temp_dir, "service-account-key.json")
        cmd = [
            "gcloud", "iam", "service-accounts", "keys", "create", self.service_account_key_path,
            "--iam-account", self.service_account_email,
            "--project", self.config.project_id
        ]
        self._run_command(cmd, "Failed to create service account key")
        
        logger.info(f"Service account created: {self.service_account_email}")
    
    def _copy_and_anonymize_data(self):
        """Copy data from production to dev environment with anonymization"""
        logger.info("Copying and anonymizing data from production environment")
        
        # First, copy the canonical company names table for anonymization
        self._copy_canonical_names_table()
        
        # Copy each specified table with anonymization
        for table_name in self.config.tables_to_copy:
            self._copy_table_with_anonymization(table_name)
        
        logger.info("Data copying and anonymization completed")
    
    def _copy_canonical_names_table(self):
        """Copy the canonical company names table for anonymization"""
        source_table = f"{self.config.source_project}.{self.config.source_dataset}.canonical_company_names_sa"
        target_table = f"{self.config.project_id}.{self.config.target_dataset}.canonical_company_names_sa"
        
        query = f"""
        CREATE OR REPLACE TABLE `{target_table}` AS
        SELECT * FROM `{source_table}`
        """
        
        self._run_bigquery_query(query, "Failed to copy canonical company names table")
    
    def _copy_table_with_anonymization(self, table_name: str):
        """Copy a table from production with company name anonymization"""
        source_table = f"{self.config.source_project}.{self.config.source_dataset}.{table_name}"
        target_table = f"{self.config.project_id}.{self.config.target_dataset}.{table_name}"
        canonical_table = f"{self.config.project_id}.{self.config.target_dataset}.canonical_company_names_sa"
        
        # Check if the source table has a company_name column
        schema_query = f"""
        SELECT column_name 
        FROM `{self.config.source_project}.{self.config.source_dataset}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_name}' AND column_name = 'company_name'
        """
        
        # For tables with company_name, apply anonymization
        query = f"""
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
        """
        
        self._run_bigquery_query(query, f"Failed to copy table: {table_name}")
        logger.info(f"Copied and anonymized table: {table_name}")
    
    def _create_github_repo(self) -> str:
        """Create GitHub repository and upload contractor files"""
        repo_name = f"contractor-{self.config.contractor_name.lower().replace(' ', '-')}-dev"
        
        # Create repository using GitHub CLI
        cmd = [
            "gh", "repo", "create", repo_name,
            "--private",
            "--description", f"Development environment for contractor {self.config.contractor_name}",
            "--clone"
        ]
        
        try:
            self._run_command(cmd, "Failed to create GitHub repository")
        except subprocess.CalledProcessError:
            logger.warning("GitHub CLI not available or not authenticated. Please create repository manually.")
            return f"https://github.com/YOUR_USERNAME/{repo_name}"
        
        # Copy files to repository
        repo_path = os.path.join(os.getcwd(), repo_name)
        self._setup_repo_files(repo_path)
        
        # Add contractor as collaborator
        if self.config.github_username:
            cmd = [
                "gh", "api", f"repos/OWNER/{repo_name}/collaborators/{self.config.github_username}",
                "--method", "PUT",
                "--field", "permission=push"
            ]
            try:
                self._run_command(cmd, "Failed to add contractor as collaborator")
            except subprocess.CalledProcessError:
                logger.warning(f"Failed to add {self.config.github_username} as collaborator. Please add manually.")
        
        return f"https://github.com/YOUR_USERNAME/{repo_name}"
    
    def _setup_repo_files(self, repo_path: str):
        """Set up files in the GitHub repository"""
        # Copy service account key
        shutil.copy2(self.service_account_key_path, os.path.join(repo_path, "service-account-key.json"))
        
        # Copy example script with updated configuration
        self._copy_and_update_example_script(repo_path)
        
        # Create README
        self._create_repo_readme(repo_path)
        
        # Create requirements.txt
        self._create_requirements_file(repo_path)
        
        # Commit and push
        os.chdir(repo_path)
        self._run_command(["git", "add", "."], "Failed to add files to git")
        self._run_command(["git", "commit", "-m", "Initial contractor environment setup"], "Failed to commit files")
        self._run_command(["git", "push", "origin", "main"], "Failed to push to GitHub")
        os.chdir("..")
    
    def _copy_and_update_example_script(self, repo_path: str):
        """Copy and update the example script with new project configuration"""
        source_script = "example_of_type_of_script_contractor_would_edit.py"
        target_script = os.path.join(repo_path, "risk_rating_calculator.py")
        
        # Read the original script
        with open(source_script, 'r') as f:
            content = f.read()
        
        # Update project references
        content = content.replace('"assembled-wh"', f'"{self.config.project_id}"')
        content = content.replace('BIGQUERY_PROJECT = "assembled-wh"', f'BIGQUERY_PROJECT = "{self.config.project_id}"')
        
        # Write updated script
        with open(target_script, 'w') as f:
            f.write(content)
    
    def _create_repo_readme(self, repo_path: str):
        """Create README for the contractor repository"""
        readme_content = f"""# Development Environment for {self.config.contractor_name}

This repository contains your development environment for working on the risk rating calculator.

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Authentication**
   - The `service-account-key.json` file is already included in this repository
   - This service account has full access to the development GCP project: `{self.config.project_id}`

3. **Running the Application**
   ```bash
   python risk_rating_calculator.py
   ```

## Project Information

- **GCP Project ID**: `{self.config.project_id}`
- **BigQuery Dataset**: `{self.config.target_dataset}`
- **Service Account**: `{self.service_account_email}`

## Available Tables

The following tables have been copied from production with anonymized company names:

{chr(10).join(f"- `{self.config.project_id}.{self.config.target_dataset}.{table}`" for table in self.config.tables_to_copy)}

## Development Guidelines

1. All company names in the data have been anonymized for privacy
2. You have full access to modify and test within this project
3. Please document any changes you make
4. Test thoroughly before requesting code review

## Support

If you have any questions or issues, please create an issue in this repository.
"""
        
        with open(os.path.join(repo_path, "README.md"), 'w') as f:
            f.write(readme_content)
    
    def _create_requirements_file(self, repo_path: str):
        """Create requirements.txt file"""
        requirements = """google-cloud-bigquery==3.11.4
google-cloud-secret-manager==2.16.4
google-auth==2.23.3
pandas==2.0.3
numpy==1.24.3
flask==2.3.3
pandas-gbq==0.19.2
"""
        
        with open(os.path.join(repo_path, "requirements.txt"), 'w') as f:
            f.write(requirements)
    
    def _generate_contractor_instructions(self) -> str:
        """Generate detailed instructions for the contractor"""
        instructions_path = f"contractor_instructions_{self.config.contractor_name.replace(' ', '_')}.md"
        
        instructions = f"""# Contractor Setup Instructions - {self.config.contractor_name}

## Environment Details

- **Project ID**: `{self.config.project_id}`
- **GitHub Repository**: [Link will be provided separately]
- **Service Account**: `{self.service_account_email}`

## Getting Started

1. **Accept GitHub Repository Invitation**
   - You should receive an email invitation to collaborate on the repository
   - Accept the invitation and clone the repository

2. **Set Up Local Environment**
   ```bash
   git clone [REPOSITORY_URL]
   cd [REPOSITORY_NAME]
   pip install -r requirements.txt
   ```

3. **Verify Access**
   ```bash
   python risk_rating_calculator.py
   ```

## What You Have Access To

- Full read/write access to BigQuery dataset `{self.config.project_id}.{self.config.target_dataset}`
- Ability to create and deploy Cloud Run services
- Access to Secret Manager for configuration
- Full project owner permissions within the development project

## Data Privacy Notes

- All company names have been anonymized using a lookup table
- Financial data is real but company identities are protected
- Do not attempt to reverse-engineer company identities

## Deliverables

Please ensure your final code:
1. Runs successfully in the development environment
2. Is well-documented with comments
3. Includes any new dependencies in requirements.txt
4. Has been tested with the provided data

## Timeline

- Setup completion: [DATE]
- Development deadline: [DATE]
- Code review: [DATE]

## Contact

For any questions or issues, please:
1. Create an issue in the GitHub repository
2. Email: [YOUR_EMAIL]

---
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        with open(instructions_path, 'w') as f:
            f.write(instructions)
        
        return instructions_path
    
    def _run_bigquery_query(self, query: str, error_message: str):
        """Run a BigQuery query using bq command line tool"""
        query_file = os.path.join(self.temp_dir, "query.sql")
        with open(query_file, 'w') as f:
            f.write(query)
        
        cmd = [
            "bq", "query",
            "--use_legacy_sql=false",
            "--project_id", self.config.project_id,
            f"--service_account_private_key_file={self.service_account_key_path}",
            f"@{query_file}"
        ]
        
        self._run_command(cmd, error_message)
    
    def _run_command(self, cmd: List[str], error_message: str) -> str:
        """Run a shell command and return output"""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=300  # 5 minute timeout
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"{error_message}: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            raise


def load_config_from_file(config_path: str) -> ContractorConfig:
    """Load contractor configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Validate that all required fields are present
        required_fields = [
            'contractor_name', 'github_username', 'project_id', 'project_name',
            'billing_account_id', 'source_project', 'source_dataset', 
            'target_dataset', 'tables_to_copy'
        ]
        
        missing_fields = [field for field in required_fields if field not in config_data]
        if missing_fields:
            raise ValueError(f"Missing required fields in config file: {missing_fields}")
        
        # Validate tables_to_copy is a list
        if not isinstance(config_data['tables_to_copy'], list):
            raise ValueError("tables_to_copy must be a list of table names")
        
        return ContractorConfig(**config_data)
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file: {e}")
    except TypeError as e:
        raise ValueError(f"Invalid configuration format: {e}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up contractor development environment")
    parser.add_argument("--config", required=True, help="Path to contractor configuration YAML file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config_from_file(args.config)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info(f"Would set up environment for: {config.contractor_name}")
        logger.info(f"Project ID: {config.project_id}")
        logger.info(f"GitHub Username: {config.github_username}")
        logger.info(f"Tables to copy: {config.tables_to_copy}")
        return
    
    # Set up environment
    setup = ContractorEnvironmentSetup(config)
    results = setup.setup_environment()
    
    # Print results
    print("\n" + "="*50)
    print("CONTRACTOR ENVIRONMENT SETUP RESULTS")
    print("="*50)
    for key, value in results.items():
        print(f"{key}: {value}")
    print("="*50)


if __name__ == "__main__":
    main() 