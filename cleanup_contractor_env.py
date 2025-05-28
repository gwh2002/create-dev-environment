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
from typing import List
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContractorEnvironmentCleanup:
    """Class for cleaning up contractor development environments"""
    
    def __init__(self, project_id: str, repo_name: str = None):
        self.project_id = project_id
        self.repo_name = repo_name or f"contractor-{project_id.split('-')[1:-2]}-dev"
    
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
            
            results["status"] = "completed"
            logger.info("Environment cleanup completed successfully!")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
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
        instruction_files = [
            f"contractor_instructions_{self.project_id.replace('-', '_')}.md",
            f"contractor_setup_{self.project_id}*.log"
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


def list_contractor_projects() -> List[str]:
    """List all contractor projects"""
    try:
        cmd = [
            "gcloud", "projects", "list", 
            "--filter=name:contractor-*",
            "--format=value(projectId)"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        projects = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        return projects
    except subprocess.CalledProcessError:
        logger.error("Failed to list projects")
        return []


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Clean up contractor development environment")
    parser.add_argument("--project-id", help="GCP project ID to clean up")
    parser.add_argument("--repo-name", help="GitHub repository name (optional)")
    parser.add_argument("--list-projects", action="store_true", help="List all contractor projects")
    parser.add_argument("--skip-repo", action="store_true", help="Skip GitHub repository archival")
    parser.add_argument("--skip-project", action="store_true", help="Skip GCP project deletion")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    if args.list_projects:
        projects = list_contractor_projects()
        if projects:
            print("Contractor projects found:")
            for project in projects:
                print(f"  - {project}")
        else:
            print("No contractor projects found")
        return
    
    if not args.project_id:
        print("Error: --project-id is required")
        parser.print_help()
        return
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info(f"Would clean up project: {args.project_id}")
        if not args.skip_repo:
            logger.info(f"Would archive repository: {args.repo_name or 'auto-detected'}")
        if not args.skip_project:
            logger.info(f"Would delete GCP project: {args.project_id}")
        return
    
    # Confirm deletion
    print(f"WARNING: This will permanently delete the contractor environment for project: {args.project_id}")
    if not args.skip_project:
        print("- GCP project and all data will be deleted")
    if not args.skip_repo:
        print("- GitHub repository will be archived")
    
    confirm = input("Are you sure you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cleanup cancelled")
        return
    
    # Perform cleanup
    cleanup = ContractorEnvironmentCleanup(args.project_id, args.repo_name)
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