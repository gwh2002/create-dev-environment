#!/bin/bash

# Setup Prerequisites for Contractor Environment Tool
# This script installs and configures the necessary tools

set -e

echo "Setting up prerequisites for contractor environment tool..."

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

echo "Detected platform: $PLATFORM"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Homebrew on macOS if not present
if [[ "$PLATFORM" == "macos" ]] && ! command_exists brew; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install Google Cloud CLI
if ! command_exists gcloud; then
    echo "Installing Google Cloud CLI..."
    if [[ "$PLATFORM" == "macos" ]]; then
        brew install google-cloud-sdk
    else
        # Linux installation
        curl https://sdk.cloud.google.com | bash
        exec -l $SHELL
    fi
else
    echo "Google Cloud CLI already installed"
fi

# Install GitHub CLI
if ! command_exists gh; then
    echo "Installing GitHub CLI..."
    if [[ "$PLATFORM" == "macos" ]]; then
        brew install gh
    else
        # Linux installation
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        sudo apt update
        sudo apt install gh
    fi
else
    echo "GitHub CLI already installed"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Authenticate with Google Cloud
echo ""
echo "Next steps:"
echo "1. Authenticate with Google Cloud:"
echo "   gcloud auth login"
echo "   gcloud auth application-default login"
echo ""
echo "2. Set your default project:"
echo "   gcloud config set project YOUR_MAIN_PROJECT_ID"
echo ""
echo "3. Get your billing account ID:"
echo "   gcloud billing accounts list"
echo ""
echo "4. Authenticate with GitHub:"
echo "   gh auth login"
echo ""
echo "5. Copy contractor_config_template.yaml and fill in the details"
echo "6. Run: python3 setup_contractor_env.py --config your_contractor_config.yaml"

echo ""
echo "Prerequisites installation completed!" 