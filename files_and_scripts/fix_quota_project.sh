#!/bin/bash

# Fix Quota Project Issues for Contractor Environments
# This script helps resolve quota project mismatches

set -e

echo "🔧 Quota Project Fix Utility"
echo "============================"

# Function to fix quota project for a specific project
fix_quota_project() {
    local project_id=$1
    echo "Setting quota project to: $project_id"
    gcloud auth application-default set-quota-project "$project_id"
    echo "✅ Quota project set successfully"
}

# Check if project ID is provided as argument
if [ $# -eq 1 ]; then
    fix_quota_project "$1"
    exit 0
fi

# Interactive mode - show current project and ask for confirmation
current_project=$(gcloud config get-value project 2>/dev/null || echo "none")
echo "Current active project: $current_project"

if [ "$current_project" != "none" ]; then
    read -p "Set quota project to match current project ($current_project)? (y/n): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        fix_quota_project "$current_project"
        exit 0
    fi
fi

# Show available contractor projects
echo ""
echo "Available contractor projects:"
gcloud projects list --filter="projectId:partner-*-dev-*" --format="table(projectId,name)" 2>/dev/null || echo "No contractor projects found"

echo ""
read -p "Enter project ID to set as quota project: " project_id

if [ -n "$project_id" ]; then
    fix_quota_project "$project_id"
else
    echo "❌ No project ID provided"
    exit 1
fi 