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
        self.service_account_email = f"contractor-{config.contractor_name.lower().replace(' ', '-')}@{config.project_id}.iam.gserviceaccount.com"
        
        # Create temporary directory for this setup
        contractor_name_safe = config.contractor_name.replace(' ', '_').replace('-', '_')
        self.temp_dir = tempfile.mkdtemp(prefix=f"contractor_setup_{contractor_name_safe}_")
        self.service_account_key_path = os.path.join(self.temp_dir, "service-account-key.json")
        
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
    def setup_environment(self) -> Dict[str, str]:
        """
        Main method to set up the complete contractor environment
        
        Returns:
            Dict containing setup results and important information
        """
        logger.info(f"Starting environment setup for contractor: {self.config.contractor_name}")
        
        try:
            # Step 1: Create GCP Project
            logger.info("Step 1: Creating GCP Project")
            self._create_gcp_project()
            
            # Step 2: Enable required APIs
            logger.info("Step 2: Enabling required APIs")
            self._enable_apis()
            
            # Step 3: Create service account
            logger.info("Step 3: Creating service account")
            self._create_service_account()
            
            # Step 4: Create BigQuery dataset
            logger.info("Step 4: Creating BigQuery dataset")
            self._create_bigquery_dataset()
            
            # Step 5: Copy and anonymize data
            logger.info("Step 5: Copying and anonymizing data")
            self._copy_and_anonymize_data()
            
            # Step 6: Create GitHub repository
            logger.info("Step 6: Creating GitHub repository")
            repo_url = self._create_github_repo()
            
            # Step 7: Generate instructions
            logger.info("Step 7: Generating contractor instructions")
            instructions_path = self._generate_contractor_instructions()
            
            results = {
                'project_id': self.config.project_id,
                'service_account_email': self.service_account_email,
                'repo_url': repo_url,
                'instructions_path': instructions_path
            }
            
            logger.info(f"Environment setup completed successfully for {self.config.contractor_name}")
            return results
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            self.cleanup_on_error()
            raise
        finally:
            # Only cleanup on success
            if 'results' in locals():
                self.cleanup()
    
    def _create_gcp_project(self):
        """Create a new GCP project or use existing one"""
        logger.info(f"Setting up GCP project: {self.config.project_id}")
        
        # Check if project already exists
        try:
            cmd = ["gcloud", "projects", "describe", self.config.project_id]
            result = self._run_command(cmd, "Failed to check project existence")
            logger.info(f"Project {self.config.project_id} already exists, skipping creation")
        except subprocess.CalledProcessError:
            # Project doesn't exist, create it
            logger.info(f"Creating new GCP project: {self.config.project_id}")
            cmd = [
                "gcloud", "projects", "create", self.config.project_id,
                "--name", self.config.project_name
            ]
            self._run_command(cmd, "Failed to create GCP project")
            logger.info(f"GCP project {self.config.project_id} created successfully")
        
        # Set as default project
        cmd = ["gcloud", "config", "set", "project", self.config.project_id]
        self._run_command(cmd, "Failed to set default project")
        
        # Link billing account (always try this in case it wasn't linked before)
        if self.config.billing_account_id:
            try:
                cmd = [
                    "gcloud", "billing", "projects", "link", self.config.project_id,
                    "--billing-account", self.config.billing_account_id
                ]
                self._run_command(cmd, "Failed to link billing account")
                logger.info("Billing account linked successfully")
            except subprocess.CalledProcessError:
                logger.warning("Billing account may already be linked or you may not have permissions")
        
        logger.info(f"GCP project {self.config.project_id} is ready")
    
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
        self.service_account_email = f"{sa_name}@{self.config.project_id}.iam.gserviceaccount.com"
        
        # Check if service account already exists
        try:
            cmd = [
                "gcloud", "iam", "service-accounts", "describe", self.service_account_email,
                "--project", self.config.project_id
            ]
            self._run_command(cmd, "Failed to check service account existence")
            logger.info(f"Service account {self.service_account_email} already exists, skipping creation")
        except subprocess.CalledProcessError:
            # Service account doesn't exist, create it
            logger.info(f"Creating service account: {self.service_account_email}")
            cmd = [
                "gcloud", "iam", "service-accounts", "create", sa_name,
                "--display-name", sa_display_name,
                "--project", self.config.project_id
            ]
            self._run_command(cmd, "Failed to create service account")
            logger.info(f"Service account {self.service_account_email} created successfully")
        
        # Grant necessary roles (always do this to ensure permissions are current)
        roles = [
            "roles/bigquery.admin",
            "roles/run.admin", 
            "roles/secretmanager.admin",
            "roles/storage.admin",
            "roles/cloudbuild.builds.editor"
        ]
        
        for role in roles:
            try:
                cmd = [
                    "gcloud", "projects", "add-iam-policy-binding", self.config.project_id,
                    "--member", f"serviceAccount:{self.service_account_email}",
                    "--role", role
                ]
                self._run_command(cmd, f"Failed to grant role: {role}")
            except subprocess.CalledProcessError:
                logger.warning(f"Role {role} may already be granted or you may not have permissions")
        
        # Create and download service account key
        self.service_account_key_path = os.path.join(self.temp_dir, "service-account-key.json")
        cmd = [
            "gcloud", "iam", "service-accounts", "keys", "create", self.service_account_key_path,
            "--iam-account", self.service_account_email,
            "--project", self.config.project_id
        ]
        self._run_command(cmd, "Failed to create service account key")
        
        # Create Secret Manager secret with the service account key
        self._create_secret_manager_secret()
        
        logger.info(f"Service account ready: {self.service_account_email}")
    
    def _create_secret_manager_secret(self):
        """Create Secret Manager secret with the service account key"""
        secret_name = "bellaventure_service_account_json"
        
        logger.info(f"Creating Secret Manager secret: {secret_name}")
        
        # Check if secret already exists
        try:
            cmd = [
                "gcloud", "secrets", "describe", secret_name,
                "--project", self.config.project_id
            ]
            self._run_command(cmd, "Failed to check secret existence")
            logger.info(f"Secret {secret_name} already exists, updating with new version")
            
            # Add new version to existing secret
            cmd = [
                "gcloud", "secrets", "versions", "add", secret_name,
                "--project", self.config.project_id,
                "--data-file", self.service_account_key_path
            ]
            self._run_command(cmd, "Failed to add new secret version")
            
        except subprocess.CalledProcessError:
            # Secret doesn't exist, create it
            logger.info(f"Creating new Secret Manager secret: {secret_name}")
            cmd = [
                "gcloud", "secrets", "create", secret_name,
                "--project", self.config.project_id,
                "--data-file", self.service_account_key_path
            ]
            self._run_command(cmd, "Failed to create Secret Manager secret")
        
        logger.info(f"Secret Manager secret {secret_name} ready")
    
    def _create_bigquery_dataset(self):
        """Create BigQuery dataset in the contractor project"""
        logger.info(f"Creating BigQuery dataset: {self.config.target_dataset}")
        
        cmd = [
            "bq", "mk", 
            "--project_id", self.config.project_id,
            "--dataset", 
            f"{self.config.project_id}:{self.config.target_dataset}"
        ]
        
        try:
            self._run_command(cmd, "Failed to create BigQuery dataset")
            logger.info(f"BigQuery dataset {self.config.target_dataset} created successfully")
        except subprocess.CalledProcessError:
            logger.info(f"BigQuery dataset {self.config.target_dataset} may already exist")
    
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
        
        query = f"CREATE OR REPLACE TABLE `{target_table}` AS SELECT * FROM `{source_table}`"
        
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
        
        # Get GitHub owner from master config
        master_config = self._load_master_config()
        github_owner = master_config.get('github_owner', 'YOUR_USERNAME')
        
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
            return f"https://github.com/{github_owner}/{repo_name}"
        
        # Copy files to repository
        repo_path = os.path.join(os.getcwd(), repo_name)
        self._setup_repo_files(repo_path)
        
        # Add contractor as collaborator
        if self.config.github_username:
            cmd = [
                "gh", "api", f"repos/{github_owner}/{repo_name}/collaborators/{self.config.github_username}",
                "--method", "PUT",
                "--field", "permission=push"
            ]
            try:
                self._run_command(cmd, "Failed to add contractor as collaborator")
            except subprocess.CalledProcessError:
                logger.warning(f"Failed to add {self.config.github_username} as collaborator. Please add manually.")
        
        return f"https://github.com/{github_owner}/{repo_name}"
    
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
        
        # Create deployment files
        self._create_dockerfile(repo_path)
        self._create_deploy_script(repo_path)
        self._create_dockerignore(repo_path)
        self._create_test_script(repo_path)
        
        # Commit and push
        os.chdir(repo_path)
        self._run_command(["git", "add", "."], "Failed to add files to git")
        self._run_command(["git", "commit", "-m", "Initial contractor environment setup"], "Failed to commit files")
        self._run_command(["git", "push", "origin", "main"], "Failed to push to GitHub")
        os.chdir("..")
    
    def _copy_and_update_example_script(self, repo_path: str):
        """Copy and update the example script with new project configuration"""
        source_script = "initial_reference/example_of_type_of_script_contractor_would_edit.py"
        target_script = os.path.join(repo_path, "risk_rating_calculator.py")
        
        # Read the original script
        with open(source_script, 'r') as f:
            content = f.read()
        
        # Update project references
        content = content.replace('"assembled-wh"', f'"{self.config.project_id}"')
        content = content.replace('BIGQUERY_PROJECT = "assembled-wh"', f'BIGQUERY_PROJECT = "{self.config.project_id}"')
        content = content.replace('CLOUD_RUN_PROJECT = "915401990209"', f'CLOUD_RUN_PROJECT = "{self.config.project_id}"')
        
        # Write updated script
        with open(target_script, 'w') as f:
            f.write(content)
    
    def _create_repo_readme(self, repo_path: str):
        """Create README for the contractor repository"""
        readme_content = f"""# Development Environment for {self.config.contractor_name}

This repository contains your development environment for working on the risk rating calculator. **This environment is designed to be production-ready and easily portable to other deployment environments.**

## 🏗️ Architecture Overview

This development environment follows production best practices to ensure your code can be seamlessly deployed to various environments (staging, production, client environments) without modification.

### Credential Management Strategy

The application uses a **dual-credential approach** for maximum portability:

1. **Primary (Production)**: Secret Manager - `bellaventure_service_account_json`
2. **Fallback (Development)**: Local file - `service-account-key.json`

This design ensures:
- ✅ **Zero code changes** when moving from development to production
- ✅ **Easy deployment** to client environments using their Secret Manager
- ✅ **Development convenience** with local files
- ✅ **Security best practices** for production deployments

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Authentication (Automatic)**
   - The application automatically handles credential loading
   - In this dev environment: Uses Secret Manager first, falls back to local file
   - In production: Will use Secret Manager seamlessly
   - No configuration changes needed!

3. **Running the Application**
   ```bash
   python risk_rating_calculator.py
   ```

## 🚀 Production Deployment

When deploying to production or client environments:

1. **Create Secret Manager secret** in target project:
   ```bash
   gcloud secrets create bellaventure_service_account_json \\
     --project=TARGET_PROJECT_ID \\
     --data-file=path/to/service-account-key.json
   ```

2. **Deploy your code** - no changes needed!
   - The application will automatically use Secret Manager
   - Same code works in development and production

3. **Environment Variables** (optional):
   ```bash
   export GOOGLE_CLOUD_PROJECT=TARGET_PROJECT_ID
   ```

## Project Information

- **GCP Project ID**: `{self.config.project_id}`
- **BigQuery Dataset**: `{self.config.target_dataset}`
- **Service Account**: `{self.service_account_email}`
- **Secret Manager Secret**: `bellaventure_service_account_json`

## Available Tables

The following tables have been copied from production with anonymized company names:

{chr(10).join(f"- `{self.config.project_id}.{self.config.target_dataset}.{table}`" for table in self.config.tables_to_copy)}
- `{self.config.project_id}.{self.config.target_dataset}.canonical_company_names_sa` (anonymization lookup)

## 🔒 Data Privacy & Security

### Anonymization
- All company names have been anonymized using a canonical lookup table
- Financial data is real and accurate, only company identities are protected
- The `canonical_company_names_sa` table maps real names to anonymized versions

### Security Features
- Service account has minimal required permissions
- Isolated development project prevents access to production
- Private repository keeps code and credentials secure
- Secret Manager provides secure credential storage

## Development Guidelines

1. **Code Portability**: Write code that works in any GCP project
   - Use environment variables for project IDs when possible
   - Leverage the automatic credential loading system
   - Avoid hardcoding project-specific values

2. **Testing**: Test thoroughly in this development environment
   - All production data patterns are represented (anonymized)
   - Same APIs and services as production
   - Identical data schemas and relationships

3. **Documentation**: Document any changes you make
   - Update this README if you add new dependencies
   - Comment your code for future maintainability
   - Note any environment-specific configurations

4. **Dependencies**: Keep `requirements.txt` updated
   - Use latest stable package versions
   - Add any new packages you install
   - Test that fresh installs work correctly

## 🔧 Troubleshooting

### Credential Issues
```bash
# Check if Secret Manager secret exists
gcloud secrets list --project={self.config.project_id}

# Verify local file exists
ls -la service-account-key.json

# Test BigQuery access
python -c "from risk_rating_calculator import get_bigquery_credentials; print('✅ Credentials loaded successfully')"
```

### Common Issues
- **Import errors**: Run `pip install -r requirements.txt`
- **Permission denied**: Ensure you're using the correct project ID
- **Table not found**: Verify table names match the available tables listed above

## 📞 Support

If you have any questions or issues:
1. Create an issue in this repository
2. Check the troubleshooting section above
3. Contact: greg@bellaventure.co

---

**Note**: This environment is designed for easy portability. The same code you develop here will work seamlessly in production environments with minimal configuration changes.

## 📦 **DELIVERABLE: Production Deployment Package**

Your final deliverable should be a complete, production-ready package that can be deployed to the client's Google Cloud environment. This repository is already configured for this purpose.

### What You Need to Deliver

1. **Complete, tested code** in this repository
2. **All deployment files** (already included):
   - `Dockerfile` - Production-ready container configuration
   - `deploy.sh` - Automated deployment script
   - `requirements.txt` - All dependencies
   - `.dockerignore` - Optimized build context

### Final Deliverable Checklist

Before marking your work complete, ensure:

- [ ] **Code works in development environment** (`python risk_rating_calculator.py`)
- [ ] **All tests pass** and functionality is verified
- [ ] **Dependencies are up to date** in `requirements.txt`
- [ ] **Code is well-documented** with comments and docstrings
- [ ] **README is updated** with any new features or requirements
- [ ] **Docker build works** (`docker build -t risk-calculator .`)
- [ ] **No hardcoded values** - all configuration uses environment variables
- [ ] **Service account key is NOT committed** (it's in `.dockerignore`)

### Client Deployment Process

The client will follow these steps to deploy your code:

1. **Copy your repository** to their organization
2. **Create Secret Manager secret** in their production project:
   ```bash
   gcloud secrets create bellaventure_service_account_json \\
     --project=CLIENT_PROJECT_ID \\
     --data-file=path/to/their/service-account-key.json
   ```
3. **Run deployment script**:
   ```bash
   export GOOGLE_CLOUD_PROJECT=CLIENT_PROJECT_ID
   ./deploy.sh
   ```

That's it! Your code will automatically:
- ✅ Use their Secret Manager for credentials
- ✅ Connect to their BigQuery datasets
- ✅ Deploy to their Cloud Run environment
- ✅ Scale automatically based on demand
"""
        
        with open(os.path.join(repo_path, "README.md"), 'w') as f:
            f.write(readme_content)
    
    def _create_requirements_file(self, repo_path: str):
        """Create requirements.txt file"""
        requirements = """google-cloud-bigquery
google-cloud-secret-manager
google-auth
pandas
numpy
flask
pandas-gbq
gunicorn
requests
"""
        
        with open(os.path.join(repo_path, "requirements.txt"), 'w') as f:
            f.write(requirements)
    
    def _create_dockerfile(self, repo_path: str):
        """Create Dockerfile for Cloud Run deployment"""
        dockerfile_content = """# Use Python 3.11 slim image for smaller size and better performance
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \\
    && chown -R app:app /app
USER app

# Expose port (Cloud Run will set PORT environment variable)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the application
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 risk_rating_calculator:app
"""
        
        with open(os.path.join(repo_path, "Dockerfile"), 'w') as f:
            f.write(dockerfile_content)

    def _create_deploy_script(self, repo_path: str):
        """Create deployment script for Cloud Run"""
        deploy_script_content = f"""#!/bin/bash

# Cloud Run Deployment Script
# This script deploys the risk rating calculator to Google Cloud Run

set -e

# Configuration - UPDATE THESE VALUES FOR YOUR ENVIRONMENT
PROJECT_ID="${{GOOGLE_CLOUD_PROJECT:-{self.config.source_project}}}"
SERVICE_NAME="risk-rating-calculator"
REGION="us-central1"
SECRET_NAME="bellaventure_service_account_json"

echo "🚀 Deploying Risk Rating Calculator to Cloud Run"
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud. Please run 'gcloud auth login'"
    exit 1
fi

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📋 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Check if secret exists
echo "🔐 Checking Secret Manager configuration..."
if ! gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "❌ Error: Secret '$SECRET_NAME' not found in project '$PROJECT_ID'"
    echo "Please create the secret first:"
    echo "gcloud secrets create $SECRET_NAME --project=$PROJECT_ID --data-file=path/to/service-account-key.json"
    exit 1
fi

# Build and deploy to Cloud Run
echo "🏗️  Building and deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \\
    --source . \\
    --platform managed \\
    --region $REGION \\
    --allow-unauthenticated \\
    --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID \\
    --memory 1Gi \\
    --cpu 1 \\
    --timeout 300 \\
    --max-instances 10 \\
    --port 8080

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "To test the deployment:"
echo "curl $SERVICE_URL/health"
"""
        
        deploy_script_path = os.path.join(repo_path, "deploy.sh")
        with open(deploy_script_path, 'w') as f:
            f.write(deploy_script_content)
        
        # Make the script executable
        os.chmod(deploy_script_path, 0o755)

    def _create_dockerignore(self, repo_path: str):
        """Create .dockerignore file"""
        dockerignore_content = """# Git files
.git
.gitignore

# Python cache
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis

# Virtual environments
venv/
env/
ENV/

# IDE files
.vscode/
.idea/
*.swp
*.swo
*~

# OS files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Documentation
README.md
*.md

# Development files
service-account-key.json
"""
        
        with open(os.path.join(repo_path, ".dockerignore"), 'w') as f:
            f.write(dockerignore_content)

    def _create_test_script(self, repo_path: str):
        """Create test script for deployment verification"""
        test_script_content = '''#!/usr/bin/env python3
"""
Test script to verify the deployment package is working correctly.
Run this before submitting your final deliverable.
"""

import os
import sys
import json
import subprocess
import requests
import time
from pathlib import Path

def test_requirements():
    """Test that all required packages can be imported"""
    print("🔍 Testing package imports...")
    
    required_packages = [
        'google.cloud.bigquery',
        'google.cloud.secretmanager', 
        'google.auth',
        'pandas',
        'numpy',
        'flask',
        'pandas_gbq',
        'gunicorn'
    ]
    
    failed_imports = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError as e:
            print(f"  ❌ {package}: {e}")
            failed_imports.append(package)
    
    if failed_imports:
        print(f"\\n❌ Failed to import: {failed_imports}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All packages imported successfully")
    return True

def test_credentials():
    """Test that credentials can be loaded"""
    print("\\n🔍 Testing credential loading...")
    
    try:
        from risk_rating_calculator import get_bigquery_credentials
        credentials = get_bigquery_credentials()
        print("✅ Credentials loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
        return False

def test_flask_app():
    """Test that Flask app starts and responds"""
    print("\\n🔍 Testing Flask app...")
    
    # Set environment for server mode
    os.environ['RUN_MODE'] = 'server'
    os.environ['PORT'] = '8081'  # Use different port to avoid conflicts
    
    try:
        # Start the Flask app in background
        import subprocess
        import time
        
        process = subprocess.Popen([
            sys.executable, 'risk_rating_calculator.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for app to start
        time.sleep(3)
        
        # Test health endpoint
        try:
            response = requests.get('http://localhost:8081/health', timeout=5)
            if response.status_code == 200:
                print("✅ Flask app health check passed")
                success = True
            else:
                print(f"❌ Health check failed with status: {response.status_code}")
                success = False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to Flask app: {e}")
            success = False
        
        # Clean up
        process.terminate()
        process.wait(timeout=5)
        
        return success
        
    except Exception as e:
        print(f"❌ Failed to test Flask app: {e}")
        return False

def test_docker_files():
    """Test that Docker files are present and valid"""
    print("\\n🔍 Testing Docker configuration...")
    
    required_files = ['Dockerfile', '.dockerignore', 'deploy.sh']
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
        else:
            print(f"  ✅ {file} exists")
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    # Check if deploy.sh is executable
    if not os.access('deploy.sh', os.X_OK):
        print("❌ deploy.sh is not executable")
        return False
    
    print("✅ All Docker files present and valid")
    return True

def test_bigquery_connection():
    """Test BigQuery connection"""
    print("\\n🔍 Testing BigQuery connection...")
    
    try:
        from google.cloud import bigquery
        from risk_rating_calculator import get_bigquery_credentials, BIGQUERY_PROJECT
        
        credentials = get_bigquery_credentials()
        client = bigquery.Client(project=BIGQUERY_PROJECT, credentials=credentials)
        
        # Test a simple query
        query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_PROJECT}.warehouse.ifms` LIMIT 1"
        result = client.query(query).result()
        
        for row in result:
            print(f"✅ BigQuery connection successful (found {row.count} rows)")
            return True
            
    except Exception as e:
        print(f"❌ BigQuery connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing deployment package...\\n")
    
    tests = [
        ("Requirements", test_requirements),
        ("Credentials", test_credentials), 
        ("Docker Files", test_docker_files),
        ("BigQuery Connection", test_bigquery_connection),
        ("Flask App", test_flask_app),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\\n" + "="*50)
    print("📋 TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\\n🎉 All tests passed! Your deployment package is ready.")
        print("\\n📦 Final checklist:")
        print("- [ ] Code is well documented")
        print("- [ ] All functionality has been tested")
        print("- [ ] README.md is updated with any changes")
        print("- [ ] No sensitive data is committed")
        return True
    else:
        print(f"\\n⚠️  {total - passed} tests failed. Please fix issues before submitting.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
'''
        
        with open(os.path.join(repo_path, "test_deployment.py"), 'w') as f:
            f.write(test_script_content)
    
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
        logger.info(f"Running BigQuery query: {query}")
        
        # Use user credentials for cross-project queries (service account doesn't have access to source project)
        cmd = [
            "bq", "query",
            "--use_legacy_sql=false",
            "--project_id", self.config.project_id,
            query
        ]
        
        try:
            self._run_command(cmd, error_message)
        except subprocess.CalledProcessError:
            logger.error(f"Failed query: {query}")
            raise
    
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
            logger.error(f"Command that failed: {' '.join(cmd)}")
            logger.error(f"Return code: {e.returncode}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            raise

    def cleanup(self):
        """Clean up temporary files"""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temporary directory")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory: {e}")
                logger.info(f"Temporary directory preserved at: {self.temp_dir}")
        
    def cleanup_on_error(self):
        """Clean up on error - preserve temp directory for debugging"""
        logger.info(f"Error occurred - temporary directory preserved at: {self.temp_dir}")
        logger.info("You can examine the files there for debugging")

    def _load_master_config(self) -> dict:
        """Load master configuration"""
        with open("config/master_config.yaml", 'r') as f:
            return yaml.safe_load(f)


def load_config_from_file(config_path: str, master_config_path: str = "config/master_config.yaml") -> ContractorConfig:
    """Load contractor configuration from YAML file, merging with master config"""
    try:
        # Load master configuration
        master_config = {}
        if os.path.exists(master_config_path):
            with open(master_config_path, 'r') as f:
                master_config = yaml.safe_load(f)
            logger.info(f"Loaded master configuration from {master_config_path}")
        else:
            logger.warning(f"Master config file not found: {master_config_path}. Using contractor config only.")
        
        # Load contractor-specific configuration
        with open(config_path, 'r') as f:
            contractor_config = yaml.safe_load(f)
        
        # Merge configurations (contractor config overrides master config)
        merged_config = merge_configurations(master_config, contractor_config)
        
        # Validate that all required fields are present
        required_fields = [
            'contractor_name', 'github_username', 'project_id', 'project_name',
            'billing_account_id', 'source_project', 'source_dataset', 
            'target_dataset', 'tables_to_copy'
        ]
        
        missing_fields = [field for field in required_fields if field not in merged_config]
        if missing_fields:
            raise ValueError(f"Missing required fields in config: {missing_fields}")
        
        # Validate tables_to_copy is a list
        if not isinstance(merged_config['tables_to_copy'], list):
            raise ValueError("tables_to_copy must be a list of table names")
        
        # Remove internal config data before creating ContractorConfig
        merged_config.pop('_master_config', None)
        merged_config.pop('_contractor_config', None)
        
        return ContractorConfig(**merged_config)
        
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file: {e}")
    except TypeError as e:
        raise ValueError(f"Invalid configuration format: {e}")


def merge_configurations(master_config: dict, contractor_config: dict) -> dict:
    """Merge master and contractor configurations, with contractor taking precedence"""
    merged = {}
    
    # Start with contractor-specific values
    contractor_name = contractor_config.get('contractor_name', 'Unknown')
    github_username = contractor_config.get('github_username', '')
    
    # Generate project ID if not provided
    if 'project_id' not in contractor_config:
        prefix = master_config.get('project_id_prefix', 'contractor')
        suffix = master_config.get('project_id_suffix', 'dev')
        safe_name = contractor_name.lower().replace(' ', '-').replace('_', '-')
        merged['project_id'] = f"{prefix}-{safe_name}-{suffix}"
    else:
        merged['project_id'] = contractor_config['project_id']
    
    # Generate project name if not provided
    if 'project_name' not in contractor_config:
        template = master_config.get('project_name_template', 'Contractor {contractor_name} Development Environment')
        merged['project_name'] = template.format(contractor_name=contractor_name)
    else:
        merged['project_name'] = contractor_config['project_name']
    
    # Set required fields from master or contractor config
    merged['contractor_name'] = contractor_name
    merged['github_username'] = github_username
    merged['billing_account_id'] = contractor_config.get('billing_account_id') or master_config.get('billing_account_id')
    merged['source_project'] = contractor_config.get('source_project') or master_config.get('source_project')
    merged['source_dataset'] = contractor_config.get('source_dataset') or master_config.get('source_dataset')
    merged['target_dataset'] = contractor_config.get('target_dataset') or master_config.get('target_dataset')
    
    # Handle tables_to_copy with contractor type support
    if 'tables_to_copy' in contractor_config:
        merged['tables_to_copy'] = contractor_config['tables_to_copy']
    elif 'contractor_type' in contractor_config:
        contractor_type = contractor_config['contractor_type']
        contractor_types = master_config.get('contractor_types', {})
        if contractor_type in contractor_types:
            merged['tables_to_copy'] = contractor_types[contractor_type].get('tables', master_config.get('default_tables', []))
        else:
            logger.warning(f"Unknown contractor type: {contractor_type}. Using default tables.")
            merged['tables_to_copy'] = master_config.get('default_tables', [])
    else:
        merged['tables_to_copy'] = master_config.get('default_tables', [])
    
    # Store additional config for use in other methods
    merged['_master_config'] = master_config
    merged['_contractor_config'] = contractor_config
    
    return merged


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up contractor development environment")
    parser.add_argument("--config", required=True, help="Path to contractor configuration YAML file")
    parser.add_argument("--master-config", default="config/master_config.yaml", help="Path to master configuration file (default: config/master_config.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config_from_file(args.config, args.master_config)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info(f"Would set up environment for: {config.contractor_name}")
        logger.info(f"Project ID: {config.project_id}")
        logger.info(f"Project Name: {config.project_name}")
        logger.info(f"GitHub Username: {config.github_username}")
        logger.info(f"Billing Account: {config.billing_account_id}")
        logger.info(f"Source Project: {config.source_project}")
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