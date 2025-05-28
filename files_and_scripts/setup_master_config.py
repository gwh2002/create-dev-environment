#!/usr/bin/env python3
"""
Interactive Master Configuration Setup

This script helps you set up your master_config.yaml file by gathering
your authentication IDs and organizational defaults interactively.
"""

import subprocess
import yaml
import os

def get_billing_accounts():
    """Get available billing accounts from gcloud"""
    try:
        result = subprocess.run(
            ["gcloud", "billing", "accounts", "list", "--format=value(name,displayName)"],
            capture_output=True, text=True, check=True
        )
        accounts = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    account_id = parts[0].split('/')[-1]  # Extract ID from full path
                    display_name = parts[1]
                    accounts.append((account_id, display_name))
        return accounts
    except subprocess.CalledProcessError:
        print("Warning: Could not fetch billing accounts. Make sure you're authenticated with gcloud.")
        return []

def get_github_username():
    """Get GitHub username from gh CLI"""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("Warning: Could not fetch GitHub username. Make sure you're authenticated with gh CLI.")
        return ""

def interactive_setup():
    """Interactive setup of master configuration"""
    print("🚀 Master Configuration Setup")
    print("=" * 50)
    print("This will help you create your master_config.yaml file.")
    print("You can always edit the file manually later.\n")
    
    config = {}
    
    # Billing Account
    print("📋 BILLING ACCOUNT SETUP")
    billing_accounts = get_billing_accounts()
    if billing_accounts:
        print("Available billing accounts:")
        for i, (account_id, display_name) in enumerate(billing_accounts, 1):
            print(f"  {i}. {account_id} ({display_name})")
        
        while True:
            try:
                choice = input(f"\nSelect billing account (1-{len(billing_accounts)}): ")
                index = int(choice) - 1
                if 0 <= index < len(billing_accounts):
                    config['billing_account_id'] = billing_accounts[index][0]
                    break
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
    else:
        config['billing_account_id'] = input("Enter your billing account ID: ")
    
    # GitHub Username
    print("\n🐙 GITHUB SETUP")
    github_username = get_github_username()
    if github_username:
        use_detected = input(f"Use detected GitHub username '{github_username}'? (y/n): ").lower().startswith('y')
        if use_detected:
            config['github_owner'] = github_username
        else:
            config['github_owner'] = input("Enter your GitHub username: ")
    else:
        config['github_owner'] = input("Enter your GitHub username: ")
    
    # Source Project Settings
    print("\n🏗️  SOURCE PROJECT SETUP")
    config['source_project'] = input("Enter your source project ID (default: assembled-wh): ") or "assembled-wh"
    config['source_dataset'] = input("Enter your source dataset (default: warehouse): ") or "warehouse"
    config['target_dataset'] = input("Enter target dataset for contractors (default: warehouse): ") or "warehouse"
    
    # Default Tables
    print("\n📊 DEFAULT TABLES")
    print("Enter the tables you want to copy to contractor environments.")
    print("Press Enter on an empty line when done.")
    
    tables = []
    default_tables = ["ifms", "ifms_consolidated", "ifms_wa", "ifms_consolidated_ttm_avg_data"]
    
    use_defaults = input(f"Use default tables {default_tables}? (y/n): ").lower().startswith('y')
    if use_defaults:
        tables = default_tables
    else:
        print("Enter table names (one per line, empty line to finish):")
        while True:
            table = input("Table name: ").strip()
            if not table:
                break
            tables.append(table)
    
    config['default_tables'] = tables
    
    # Project Naming
    print("\n🏷️  PROJECT NAMING")
    config['project_id_prefix'] = input("Project ID prefix (default: contractor): ") or "contractor"
    config['project_id_suffix'] = input("Project ID suffix (default: dev-2024): ") or "dev-2024"
    
    # Contact Info
    print("\n📧 CONTACT INFORMATION")
    config['contact_info'] = {
        'email': input("Your email address: "),
        'slack': input("Your Slack handle (optional): ") or ""
    }
    
    # Build full configuration
    full_config = {
        'billing_account_id': config['billing_account_id'],
        'github_owner': config['github_owner'],
        'source_project': config['source_project'],
        'source_dataset': config['source_dataset'],
        'target_dataset': config['target_dataset'],
        'default_tables': config['default_tables'],
        'project_id_prefix': config['project_id_prefix'],
        'project_id_suffix': config['project_id_suffix'],
        'project_name_template': "Contractor {contractor_name} Development Environment",
        'contractor_roles': [
            "roles/bigquery.admin",
            "roles/run.admin",
            "roles/secretmanager.admin",
            "roles/storage.admin",
            "roles/cloudbuild.builds.editor"
        ],
        'github_repo_settings': {
            'private': True,
            'default_branch': "main"
        },
        'contractor_types': {
            'standard': {
                'tables': config['default_tables'],
                'roles': [
                    "roles/bigquery.admin",
                    "roles/run.admin"
                ]
            }
        },
        'contact_info': config['contact_info'],
        'notifications': {
            'slack_webhook': "",
            'email_notifications': True
        }
    }
    
    return full_config

def main():
    """Main entry point"""
    config_path = 'config/master_config.yaml'
    
    if os.path.exists(config_path):
        print(f"✅ Master configuration already exists at {config_path}")
        
        # Show current config summary
        try:
            with open(config_path, 'r') as f:
                existing_config = yaml.safe_load(f)
            
            print("\nCurrent configuration summary:")
            print(f"  • Billing Account: {existing_config.get('billing_account_id', 'Not set')}")
            print(f"  • GitHub Owner: {existing_config.get('github_owner', 'Not set')}")
            print(f"  • Source Project: {existing_config.get('source_project', 'Not set')}")
            print(f"  • Contact Email: {existing_config.get('contact_info', {}).get('email', 'Not set')}")
            
        except Exception as e:
            print(f"  (Could not read existing config: {e})")
        
        print("\nWhat would you like to do?")
        print("1. Keep existing configuration (recommended)")
        print("2. View full configuration file")
        print("3. Reconfigure from scratch (overwrites existing)")
        print("4. Exit")
        
        while True:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                print("✅ Keeping existing configuration. You're ready to create contractor environments!")
                print("\nNext steps:")
                print("1. Copy config/contractor_config_simple_template.yaml for each contractor")
                print("2. Run: python3 files_and_scripts/setup_contractor_env.py --config contractor_config.yaml")
                return
            
            elif choice == "2":
                print(f"\n📄 Contents of {config_path}:")
                print("-" * 50)
                try:
                    with open(config_path, 'r') as f:
                        print(f.read())
                except Exception as e:
                    print(f"Error reading file: {e}")
                print("-" * 50)
                continue  # Go back to menu
            
            elif choice == "3":
                confirm = input("Are you sure you want to overwrite the existing configuration? (y/n): ")
                if confirm.lower().startswith('y'):
                    break  # Continue with setup
                else:
                    print("Setup cancelled.")
                    return
            
            elif choice == "4":
                print("Setup cancelled.")
                return
            
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
    
    # Ensure config directory exists
    os.makedirs('config', exist_ok=True)
    
    config = interactive_setup()
    
    # Write configuration file
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✅ Master configuration saved to {config_path}")
    print("\nNext steps:")
    print(f"1. Review and edit {config_path} if needed")
    print("2. Copy config/contractor_config_simple_template.yaml for each contractor")
    print("3. Run: python3 files_and_scripts/setup_contractor_env.py --config contractor_config.yaml")
    
    # Security reminder
    print("\n🔒 SECURITY REMINDER:")
    print(f"- Add {config_path} to your .gitignore file")
    print("- Keep this file secure as it contains sensitive information")

if __name__ == "__main__":
    main() 