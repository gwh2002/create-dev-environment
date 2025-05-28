#!/bin/bash

# Example Setup Script - Complete Workflow Demonstration
# This script shows the complete process from initial setup to contractor environment creation

set -e  # Exit on any error

echo "🚀 Contractor Environment Setup - Complete Example"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}📋 STEP: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [[ ! -f "files_and_scripts/setup_contractor_env.py" ]]; then
    print_error "Please run this script from the create-dev-environment directory"
    exit 1
fi

print_step "1. Installing Prerequisites"
echo "Installing required tools and dependencies..."

# Make setup script executable and run it
chmod +x files_and_scripts/setup_prerequisites.sh
./files_and_scripts/setup_prerequisites.sh

print_success "Prerequisites installed"

print_step "2. Authentication Setup"
echo "Setting up authentication with GCP and GitHub..."

# Check if already authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo "Please authenticate with Google Cloud:"
    gcloud auth login
    gcloud auth application-default login
else
    print_success "Already authenticated with Google Cloud"
fi

# Set default project
echo "Please set your default GCP project:"
echo "Available projects:"
gcloud projects list --format="table(projectId,name)"
echo ""
read -p "Enter your main project ID: " MAIN_PROJECT
gcloud config set project "$MAIN_PROJECT"

# Check GitHub authentication
if ! gh auth status >/dev/null 2>&1; then
    echo "Please authenticate with GitHub:"
    gh auth login
else
    print_success "Already authenticated with GitHub"
fi

print_step "3. Master Configuration Setup"
echo "Setting up your master configuration..."

if [[ -f "config/master_config.yaml" ]]; then
    print_warning "config/master_config.yaml already exists"
    read -p "Do you want to recreate it? (y/n): " RECREATE
    if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
        python3 files_and_scripts/setup_master_config.py
    fi
else
    python3 files_and_scripts/setup_master_config.py
fi

print_success "Master configuration complete"

print_step "4. Example Contractor Setup"
echo "Creating an example contractor environment..."

# Create example contractor config
EXAMPLE_CONFIG="config/example_contractor.yaml"
cat > "$EXAMPLE_CONFIG" << EOF
# Example Contractor Configuration
contractor_name: "Jane Doe"
github_username: "janedoe123"

# Optional: Uncomment to override defaults
# contractor_type: "analytics_specialist"
# tables_to_copy:
#   - "ifms"
#   - "ifms_consolidated"
#   - "custom_table"
EOF

print_success "Created example contractor config: $EXAMPLE_CONFIG"

# Show what would be created (dry run)
print_step "5. Dry Run - Preview"
echo "Running dry run to show what would be created..."
python3 files_and_scripts/setup_contractor_env.py --config "$EXAMPLE_CONFIG" --dry-run

echo ""
print_warning "This was a DRY RUN - no resources were actually created"
echo ""

# Ask if user wants to proceed with actual creation
read -p "Do you want to create the actual contractor environment? (y/n): " CREATE_ACTUAL
if [[ "$CREATE_ACTUAL" =~ ^[Yy]$ ]]; then
    print_step "6. Creating Actual Environment"
    echo "Creating contractor environment for Jane Doe..."
    
    # Run actual setup
    python3 files_and_scripts/setup_contractor_env.py --config "$EXAMPLE_CONFIG"
    
    print_success "Contractor environment created successfully!"
    
    # Show cleanup command
    echo ""
    print_step "7. Cleanup Information"
    echo "When the project is complete, you can clean up with:"
    echo "python3 files_and_scripts/cleanup_contractor_env.py --project-id contractor-jane-doe-dev-2024"
    
else
    print_step "6. Skipping Actual Creation"
    echo "You can create the environment later with:"
    echo "python3 files_and_scripts/setup_contractor_env.py --config $EXAMPLE_CONFIG"
fi

echo ""
print_step "8. Next Steps"
echo "To create more contractor environments:"
echo ""
echo "1. Copy the simple template:"
echo "   cp config/contractor_config_simple_template.yaml config/new_contractor.yaml"
echo ""
echo "2. Edit with contractor details:"
echo "   # Only need to change contractor_name and github_username"
echo ""
echo "3. Create environment:"
echo "   python3 files_and_scripts/setup_contractor_env.py --config config/new_contractor.yaml"
echo ""
echo "4. When done, cleanup:"
echo "   python3 files_and_scripts/cleanup_contractor_env.py --project-id PROJECT_ID"

echo ""
print_success "Setup complete! 🎉"
echo ""
echo "📁 Files created:"
echo "  - config/master_config.yaml (your authentication & defaults)"
echo "  - $EXAMPLE_CONFIG (example contractor config)"
echo ""
echo "🔒 Security reminders:"
echo "  - config/master_config.yaml contains sensitive information"
echo "  - It's already in .gitignore to prevent accidental commits"
echo "  - Keep your authentication tokens secure"
echo ""
echo "📖 For more information, see README.md" 