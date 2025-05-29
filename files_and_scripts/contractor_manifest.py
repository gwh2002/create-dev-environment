#!/usr/bin/env python3
"""
Contractor Environment Manifest Management

This module manages a manifest file that tracks all contractor environments
created and cleaned up. This provides robust tracking even if naming conventions
change or resources are manually modified.
"""

import os
import yaml
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class ContractorEnvironment:
    """Data class representing a contractor environment"""
    contractor_name: str
    project_id: str
    project_name: str
    github_username: str
    github_repo_name: str
    service_account_email: str
    creation_date: str
    status: str  # 'active', 'completed', 'deleted'
    billing_account_id: str
    source_project: str
    target_dataset: str
    tables_copied: List[str]
    cleanup_date: Optional[str] = None
    notes: Optional[str] = None

class ContractorManifest:
    """Manages the contractor environments manifest file"""
    
    def __init__(self, manifest_path: str = "contractor_environments.yaml"):
        self.manifest_path = manifest_path
        self.environments = self._load_manifest()
    
    def _load_manifest(self) -> Dict[str, ContractorEnvironment]:
        """Load the manifest file"""
        if not os.path.exists(self.manifest_path):
            logger.info(f"Manifest file not found at {self.manifest_path}, creating new one")
            return {}
        
        try:
            with open(self.manifest_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            environments = {}
            for project_id, env_data in data.items():
                # Convert dict back to ContractorEnvironment
                environments[project_id] = ContractorEnvironment(**env_data)
            
            logger.info(f"Loaded {len(environments)} environments from manifest")
            return environments
            
        except Exception as e:
            logger.error(f"Error loading manifest: {e}")
            logger.info("Starting with empty manifest")
            return {}
    
    def _save_manifest(self):
        """Save the manifest file"""
        try:
            # Convert ContractorEnvironment objects to dicts
            data = {}
            for project_id, env in self.environments.items():
                data[project_id] = asdict(env)
            
            # Create backup if file exists
            if os.path.exists(self.manifest_path):
                backup_path = f"{self.manifest_path}.backup"
                import shutil
                shutil.copy2(self.manifest_path, backup_path)
            
            with open(self.manifest_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Saved manifest with {len(self.environments)} environments")
            
        except Exception as e:
            logger.error(f"Error saving manifest: {e}")
            raise
    
    def add_environment(self, environment: ContractorEnvironment):
        """Add a new contractor environment to the manifest"""
        self.environments[environment.project_id] = environment
        self._save_manifest()
        logger.info(f"Added environment for {environment.contractor_name} ({environment.project_id})")
    
    def remove_environment(self, project_id: str, cleanup_date: str = None):
        """Mark an environment as deleted"""
        if project_id in self.environments:
            self.environments[project_id].status = 'deleted'
            self.environments[project_id].cleanup_date = cleanup_date or datetime.now().isoformat()
            self._save_manifest()
            logger.info(f"Marked environment {project_id} as deleted")
        else:
            logger.warning(f"Environment {project_id} not found in manifest")
    
    def get_environment(self, project_id: str) -> Optional[ContractorEnvironment]:
        """Get environment by project ID"""
        return self.environments.get(project_id)
    
    def find_by_contractor_name(self, contractor_name: str) -> List[ContractorEnvironment]:
        """Find environments by contractor name"""
        matches = []
        for env in self.environments.values():
            if env.contractor_name.lower() == contractor_name.lower():
                matches.append(env)
        return matches
    
    def list_active_environments(self) -> List[ContractorEnvironment]:
        """List all active environments"""
        return [env for env in self.environments.values() if env.status == 'active']
    
    def list_all_environments(self) -> List[ContractorEnvironment]:
        """List all environments"""
        return list(self.environments.values())
    
    def update_environment_status(self, project_id: str, status: str, notes: str = None):
        """Update environment status"""
        if project_id in self.environments:
            self.environments[project_id].status = status
            if notes:
                self.environments[project_id].notes = notes
            self._save_manifest()
            logger.info(f"Updated {project_id} status to {status}")
    
    def search_environments(self, query: str) -> List[ContractorEnvironment]:
        """Search environments by name, project ID, or GitHub username"""
        query_lower = query.lower()
        matches = []
        
        for env in self.environments.values():
            if (query_lower in env.contractor_name.lower() or 
                query_lower in env.project_id.lower() or 
                query_lower in env.github_username.lower()):
                matches.append(env)
        
        return matches
    
    def get_manifest_stats(self) -> Dict[str, int]:
        """Get statistics about the manifest"""
        stats = {
            'total': len(self.environments),
            'active': len([e for e in self.environments.values() if e.status == 'active']),
            'completed': len([e for e in self.environments.values() if e.status == 'completed']),
            'deleted': len([e for e in self.environments.values() if e.status == 'deleted'])
        }
        return stats
    
    def export_to_csv(self, output_path: str):
        """Export manifest to CSV for reporting"""
        import csv
        
        fieldnames = [
            'contractor_name', 'project_id', 'github_username', 'creation_date', 
            'status', 'cleanup_date', 'billing_account_id', 'notes'
        ]
        
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for env in self.environments.values():
                row = {
                    'contractor_name': env.contractor_name,
                    'project_id': env.project_id,
                    'github_username': env.github_username,
                    'creation_date': env.creation_date,
                    'status': env.status,
                    'cleanup_date': env.cleanup_date or '',
                    'billing_account_id': env.billing_account_id,
                    'notes': env.notes or ''
                }
                writer.writerow(row)
        
        logger.info(f"Exported manifest to {output_path}")

def create_environment_from_config(config, setup_results: Dict) -> ContractorEnvironment:
    """Create ContractorEnvironment from setup config and results"""
    from files_and_scripts.setup_contractor_env import ResourceNaming
    
    naming = ResourceNaming(
        contractor_name=config.contractor_name,
        project_id=config.project_id
    )
    
    return ContractorEnvironment(
        contractor_name=config.contractor_name,
        project_id=config.project_id,
        project_name=config.project_name,
        github_username=config.github_username,
        github_repo_name=naming.github_repo_name,
        service_account_email=setup_results.get('service_account_email', naming.service_account_email),
        creation_date=datetime.now().isoformat(),
        status='active',
        billing_account_id=config.billing_account_id,
        source_project=config.source_project,
        target_dataset=config.target_dataset,
        tables_copied=config.tables_to_copy
    )

def main():
    """CLI for manifest management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage contractor environment manifest")
    parser.add_argument("--list", action="store_true", help="List all environments")
    parser.add_argument("--active", action="store_true", help="List active environments only")
    parser.add_argument("--search", help="Search environments")
    parser.add_argument("--stats", action="store_true", help="Show manifest statistics")
    parser.add_argument("--export-csv", help="Export to CSV file")
    parser.add_argument("--manifest-path", default="contractor_environments.yaml", help="Path to manifest file")
    
    args = parser.parse_args()
    
    manifest = ContractorManifest(args.manifest_path)
    
    if args.stats:
        stats = manifest.get_manifest_stats()
        print("Manifest Statistics:")
        print(f"  Total environments: {stats['total']}")
        print(f"  Active: {stats['active']}")
        print(f"  Completed: {stats['completed']}")
        print(f"  Deleted: {stats['deleted']}")
    
    elif args.search:
        environments = manifest.search_environments(args.search)
        print(f"Found {len(environments)} environments matching '{args.search}':")
        for env in environments:
            print(f"  {env.contractor_name} ({env.project_id}) - {env.status}")
    
    elif args.active:
        environments = manifest.list_active_environments()
        print(f"Active environments ({len(environments)}):")
        for env in environments:
            print(f"  {env.contractor_name} ({env.project_id}) - Created: {env.creation_date}")
    
    elif args.list:
        environments = manifest.list_all_environments()
        print(f"All environments ({len(environments)}):")
        for env in environments:
            status_info = f"{env.status}"
            if env.cleanup_date:
                status_info += f" (cleaned up: {env.cleanup_date})"
            print(f"  {env.contractor_name} ({env.project_id}) - {status_info}")
    
    elif args.export_csv:
        manifest.export_to_csv(args.export_csv)
        print(f"Exported manifest to {args.export_csv}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 