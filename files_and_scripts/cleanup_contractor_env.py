#!/usr/bin/env python3
"""
Contractor Environment Cleanup Tool

This script safely removes contractor development environments when projects are completed.
It handles GCP project deletion, GitHub repository archival, and cleanup of local files.
"""

import os
import logging
import subprocess
import argparse
from typing import List, Dict, Optional
import yaml
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import manifest management
try:
    from contractor_manifest import ContractorManifest, ContractorEnvironment
    MANIFEST_AVAILABLE = True
except ImportError:
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__)))
        from contractor_manifest import ContractorManifest, ContractorEnvironment
        MANIFEST_AVAILABLE = True
    except ImportError:
        logger.warning("Manifest system not available, using fallback discovery")
        MANIFEST_AVAILABLE = False

# SHARED NAMING SYSTEM (same as setup script)
class ResourceNaming:
    """Centralized naming system for all GCP resources"""
    
    def __init__(self, contractor_name: str, project_id: str, organization_prefix: str = "bellaventure"):
        self.contractor_name = contractor_name
        self.project_id = project_id
        self.organization_prefix = organization_prefix
        
        # Create safe versions of names for different contexts
        self.contractor_name_safe = self._make_safe_name(contractor_name)
        self.contractor_name_kebab = self._make_kebab_case(contractor_name)
        self.contractor_name_snake = self._make_snake_case(contractor_name)
    
    def _make_safe_name(self, name: str) -> str:
        """Make a name safe for GCP resources (alphanumeric + hyphens)"""
        return re.sub(r'[^a-zA-Z0-9-]', '-', name.lower()).strip('-')
    
    def _make_kebab_case(self, name: str) -> str:
        """Convert to kebab-case (lowercase with hyphens)"""
        return re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
    
    def _make_snake_case(self, name: str) -> str:
        """Convert to snake_case (lowercase with underscores)"""
        return re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')
    
    @property
    def github_repo_name(self) -> str:
        """GitHub repository name"""
        return f"contractor-{self.contractor_name_kebab}-dev"
    
    @property
    def instructions_filename(self) -> str:
        """Contractor instructions filename"""
        return f"contractor_instructions_{self.contractor_name_snake}.md"

class ProjectDiscovery:
    """Enhanced project discovery using actual naming patterns"""
    
    def __init__(self, master_config_path: str = "config/master_config.yaml"):
        self.master_config = self._load_master_config(master_config_path)
        self.project_prefix = self.master_config.get('project_id_prefix', 'contractor')
        self.project_suffix = self.master_config.get('project_id_suffix', 'dev')
    
    def _load_master_config(self, config_path: str) -> dict:
        """Load master configuration"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Master config not found at {config_path}, using defaults")
            return {}
    
    def find_contractor_projects(self) -> List[Dict[str, str]]:
        """Find all contractor projects using actual naming patterns"""
        all_projects = []
        
        # Try different naming patterns based on configuration
        patterns = [
            f"{self.project_prefix}-*-{self.project_suffix}",  # e.g., partner-*-dev-2025
            f"{self.project_prefix}-*-dev",                    # e.g., partner-*-dev
            "contractor-*-dev",                                # legacy pattern
            "contractor-*",                                    # fallback
        ]
        
        for pattern in patterns:
            try:
                cmd = [
                    "gcloud", "projects", "list", 
                    f"--filter=projectId:{pattern}",
                    "--format=json"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                if result.stdout.strip():
                    import json
                    projects = json.loads(result.stdout)
                    for project in projects:
                        project_info = {
                            'project_id': project['projectId'],
                            'name': project['name'],
                            'pattern': pattern,
                            'contractor_name': self._extract_contractor_name(project['projectId'])
                        }
                        all_projects.append(project_info)
                        
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                logger.debug(f"Pattern {pattern} failed: {e}")
                continue
        
        return all_projects
    
    def _extract_contractor_name(self, project_id: str) -> str:
        """Extract contractor name from project ID"""
        # Remove prefix and suffix to get the contractor name
        name_part = project_id
        
        # Remove prefix
        if name_part.startswith(f"{self.project_prefix}-"):
            name_part = name_part[len(f"{self.project_prefix}-"):]
        elif name_part.startswith("contractor-"):
            name_part = name_part[len("contractor-"):]
        
        # Remove suffix
        if name_part.endswith(f"-{self.project_suffix}"):
            name_part = name_part[:-len(f"-{self.project_suffix}")]
        elif name_part.endswith("-dev"):
            name_part = name_part[:-4]
        
        # Convert kebab-case to title case
        return ' '.join(word.capitalize() for word in name_part.split('-'))
    
    def generate_project_id(self, contractor_name: str) -> str:
        """Generate project ID for a contractor name using current patterns"""
        safe_name = re.sub(r'[^a-zA-Z0-9]+', '-', contractor_name.lower()).strip('-')
        return f"{self.project_prefix}-{safe_name}-{self.project_suffix}"

class ContractorEnvironmentCleanup:
    """Class for cleaning up contractor development environments"""
    
    def __init__(self, project_id: str, repo_name: str = None, contractor_name: str = None):
        self.project_id = project_id
        self.contractor_name = contractor_name
        
        # Initialize manifest if available
        self.manifest = None
        if MANIFEST_AVAILABLE:
            try:
                self.manifest = ContractorManifest()
                # Get environment details from manifest if we don't have contractor name
                if not contractor_name:
                    env = self.manifest.get_environment(project_id)
                    if env:
                        self.contractor_name = env.contractor_name
                        logger.info(f"Found contractor name in manifest: {self.contractor_name}")
            except Exception as e:
                logger.warning(f"Could not initialize manifest: {e}")
        
        # If contractor name is provided, use naming system
        if self.contractor_name:
            self.naming = ResourceNaming(
                contractor_name=self.contractor_name,
                project_id=project_id,
                organization_prefix="bellaventure"
            )
            self.repo_name = repo_name or self.naming.github_repo_name
        else:
            # Fallback to old logic if no contractor name
            self.repo_name = repo_name or f"contractor-{project_id.split('-')[1:-1]}-dev"
    
    def cleanup_environment(self, archive_repo: bool = True, delete_project: bool = True) -> dict:
        """
        Clean up the contractor environment
        
        Args:
            archive_repo: Whether to archive the GitHub repository
            delete_project: Whether to delete the GCP project
            
        Returns:
            Dict containing cleanup results
        """
        results = {
            "project_id": self.project_id,
            "repo_name": self.repo_name,
            "contractor_name": self.contractor_name,
            "status": "in_progress"
        }
        
        try:
            if archive_repo:
                logger.info("Step 1: Archiving GitHub repository")
                self._archive_github_repo()
                results["repo_archived"] = True
            
            if delete_project:
                logger.info("Step 2: Deleting GCP project")
                self._delete_gcp_project()
                results["project_deleted"] = True
            
            logger.info("Step 3: Cleaning up local files")
            self._cleanup_local_files()
            results["local_files_cleaned"] = True
            
            # Step 4: Update manifest
            if self.manifest:
                logger.info("Step 4: Updating manifest")
                self.manifest.remove_environment(self.project_id)
                results["manifest_updated"] = True
            
            results["status"] = "completed"
            logger.info("Environment cleanup completed successfully!")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
            
            # Update manifest with failure status if possible
            if self.manifest:
                try:
                    self.manifest.update_environment_status(
                        self.project_id, 
                        "cleanup_failed", 
                        f"Cleanup failed: {str(e)}"
                    )
                except Exception:
                    pass  # Don't fail the whole operation if manifest update fails
            
            raise
        
        return results
    
    def _archive_github_repo(self):
        """Archive the GitHub repository"""
        logger.info(f"Archiving repository: {self.repo_name}")
        
        # Archive the repository using GitHub CLI
        cmd = [
            "gh", "repo", "archive", self.repo_name,
            "--yes"
        ]
        
        try:
            self._run_command(cmd, "Failed to archive GitHub repository")
            logger.info(f"Repository {self.repo_name} archived successfully")
        except subprocess.CalledProcessError:
            logger.warning("GitHub CLI not available or repository not found. Please archive manually.")
    
    def _delete_gcp_project(self):
        """Delete the GCP project"""
        logger.info(f"Deleting GCP project: {self.project_id}")
        
        # First, get project info to confirm it exists
        try:
            cmd = ["gcloud", "projects", "describe", self.project_id]
            self._run_command(cmd, "Project not found")
        except subprocess.CalledProcessError:
            logger.warning(f"Project {self.project_id} not found or already deleted")
            return
        
        # Delete the project
        cmd = [
            "gcloud", "projects", "delete", self.project_id,
            "--quiet"
        ]
        
        self._run_command(cmd, "Failed to delete GCP project")
        logger.info(f"GCP project {self.project_id} deleted successfully")
    
    def _cleanup_local_files(self):
        """Clean up local files related to the contractor"""
        # Remove any local repository clones
        if os.path.exists(self.repo_name):
            import shutil
            shutil.rmtree(self.repo_name)
            logger.info(f"Removed local repository clone: {self.repo_name}")
        
        # Remove contractor instruction files
        if hasattr(self, 'naming'):
            instruction_files = [self.naming.instructions_filename]
        else:
            # Fallback patterns
            safe_project = self.project_id.replace('-', '_')
            instruction_files = [
                f"contractor_instructions_{safe_project}.md",
                f"contractor_setup_{safe_project}*.log"
            ]
        
        for pattern in instruction_files:
            import glob
            for file_path in glob.glob(pattern):
                os.remove(file_path)
                logger.info(f"Removed file: {file_path}")
    
    def _run_command(self, cmd: List[str], error_message: str) -> str:
        """Run a shell command and return output"""
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=60
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"{error_message}: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            raise


def list_contractor_projects(master_config_path: str = "config/master_config.yaml") -> List[Dict[str, str]]:
    """List all contractor projects using manifest first, then fallback to discovery"""
    projects = []
    
    # Primary method: Use manifest if available
    if MANIFEST_AVAILABLE:
        try:
            manifest = ContractorManifest()
            environments = manifest.list_active_environments()
            
            if environments:
                logger.info(f"Found {len(environments)} environments in manifest")
                for env in environments:
                    projects.append({
                        'project_id': env.project_id,
                        'contractor_name': env.contractor_name,
                        'name': env.project_name,
                        'pattern': 'manifest',
                        'creation_date': env.creation_date,
                        'github_repo': env.github_repo_name,
                        'github_username': env.github_username
                    })
                return projects
            else:
                logger.info("No active environments found in manifest, trying discovery")
        except Exception as e:
            logger.warning(f"Manifest lookup failed: {e}, falling back to discovery")
    
    # Fallback method: Use discovery
    logger.info("Using discovery method to find contractor projects")
    discovery = ProjectDiscovery(master_config_path)
    discovered_projects = discovery.find_contractor_projects()
    
    # Convert discovery format to unified format
    for project in discovered_projects:
        projects.append({
            'project_id': project['project_id'],
            'contractor_name': project['contractor_name'],
            'name': project['name'],
            'pattern': project['pattern'],
            'creation_date': 'unknown',
            'github_repo': 'unknown',
            'github_username': 'unknown'
        })
    
    return projects


def find_project_by_contractor_name(contractor_name: str, master_config_path: str = "config/master_config.yaml") -> Optional[str]:
    """Find project ID by contractor name using manifest first, then discovery"""
    
    # Primary method: Use manifest if available
    if MANIFEST_AVAILABLE:
        try:
            manifest = ContractorManifest()
            environments = manifest.find_by_contractor_name(contractor_name)
            
            # Return the first active environment found
            for env in environments:
                if env.status == 'active':
                    logger.info(f"Found project for {contractor_name} in manifest: {env.project_id}")
                    return env.project_id
            
            if environments:
                logger.warning(f"Found environments for {contractor_name} but none are active")
        except Exception as e:
            logger.warning(f"Manifest lookup failed: {e}, falling back to discovery")
    
    # Fallback method: Use discovery
    logger.info("Using discovery method to find project")
    discovery = ProjectDiscovery(master_config_path)
    expected_project_id = discovery.generate_project_id(contractor_name)
    
    # Check if the expected project exists
    try:
        cmd = ["gcloud", "projects", "describe", expected_project_id]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return expected_project_id
    except subprocess.CalledProcessError:
        # Try to find it in the list of all contractor projects
        projects = discovery.find_contractor_projects()
        for project in projects:
            if project['contractor_name'].lower() == contractor_name.lower():
                return project['project_id']
        return None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Clean up contractor development environment")
    parser.add_argument("--project-id", help="GCP project ID to clean up")
    parser.add_argument("--contractor-name", help="Contractor name (will auto-find project)")
    parser.add_argument("--repo-name", help="GitHub repository name (optional)")
    parser.add_argument("--list-projects", action="store_true", help="List all contractor projects")
    parser.add_argument("--skip-repo", action="store_true", help="Skip GitHub repository archival")
    parser.add_argument("--skip-project", action="store_true", help="Skip GCP project deletion")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--master-config", default="config/master_config.yaml", help="Path to master config file")
    
    args = parser.parse_args()
    
    if args.list_projects:
        projects = list_contractor_projects(args.master_config)
        if projects:
            print("Contractor projects found:")
            print(f"{'Project ID':<35} {'Contractor':<20} {'Created':<12} {'Source':<10}")
            print("-" * 80)
            for project in projects:
                created = project.get('creation_date', 'unknown')
                if created != 'unknown' and 'T' in created:
                    created = created.split('T')[0]  # Just the date part
                source = project.get('pattern', 'discovery')
                print(f"{project['project_id']:<35} {project['contractor_name']:<20} {created:<12} {source:<10}")
        else:
            print("No contractor projects found")
        return
    
    # Determine project ID
    project_id = args.project_id
    contractor_name = args.contractor_name
    
    if not project_id and contractor_name:
        project_id = find_project_by_contractor_name(contractor_name, args.master_config)
        if not project_id:
            print(f"Error: Could not find project for contractor '{contractor_name}'")
            
            # Try to find similar names or show all available
            projects = list_contractor_projects(args.master_config)
            if projects:
                print("\nAvailable contractors:")
                for i, project in enumerate(projects, 1):
                    created = project.get('creation_date', 'unknown')
                    if created != 'unknown' and 'T' in created:
                        created = created.split('T')[0]
                    print(f"  {i}. {project['contractor_name']} ({project['project_id']}) - {created}")
                
                # Interactive selection
                try:
                    choice = input(f"\nSelect environment to clean up (1-{len(projects)}) or press Enter to cancel: ").strip()
                    if choice and choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(projects):
                            project_id = projects[idx]['project_id']
                            contractor_name = projects[idx]['contractor_name']
                            print(f"Selected: {contractor_name} ({project_id})")
                        else:
                            print("Invalid selection")
                            return
                    else:
                        print("Cancelled")
                        return
                except KeyboardInterrupt:
                    print("\nCancelled")
                    return
            else:
                print("No contractor environments found")
            return
        print(f"Found project for {contractor_name}: {project_id}")
    
    if not project_id:
        print("Error: Either --project-id or --contractor-name is required")
        parser.print_help()
        return
    
    # Extract contractor name from project if not provided
    if not contractor_name:
        discovery = ProjectDiscovery(args.master_config)
        contractor_name = discovery._extract_contractor_name(project_id)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info(f"Would clean up project: {project_id}")
        logger.info(f"Contractor: {contractor_name}")
        if not args.skip_repo:
            logger.info(f"Would archive repository: {args.repo_name or 'auto-detected'}")
        if not args.skip_project:
            logger.info(f"Would delete GCP project: {project_id}")
        return
    
    # Confirm deletion
    print(f"WARNING: This will permanently delete the contractor environment for:")
    print(f"  Contractor: {contractor_name}")
    print(f"  Project ID: {project_id}")
    if not args.skip_project:
        print("- GCP project and all data will be deleted")
    if not args.skip_repo:
        print("- GitHub repository will be archived")
    
    confirm = input("Are you sure you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cleanup cancelled")
        return
    
    # Perform cleanup
    cleanup = ContractorEnvironmentCleanup(project_id, args.repo_name, contractor_name)
    results = cleanup.cleanup_environment(
        archive_repo=not args.skip_repo,
        delete_project=not args.skip_project
    )
    
    # Print results
    print("\n" + "="*50)
    print("CONTRACTOR ENVIRONMENT CLEANUP RESULTS")
    print("="*50)
    for key, value in results.items():
        print(f"{key}: {value}")
    print("="*50)


if __name__ == "__main__":
    main() 