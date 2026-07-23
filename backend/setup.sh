#!/bin/bash
# Setup script for GCM Web UI Backend
# This script helps set up the development environment

set -e  # Exit on error

echo "========================================="
echo "GCM Web UI Backend Setup"
echo "========================================="
echo ""

# Check if we're in the correct directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Please run this script from the webui/backend directory"
    exit 1
fi

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if virtual environment exists in project root
if [ ! -d "../../venv" ]; then
    echo ""
    echo "Creating virtual environment in project root..."
    cd ../..
    python3 -m venv venv
    cd ../backend
    echo "Virtual environment created at ../../venv"
else
    echo "Virtual environment already exists at ../../venv"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source ../../venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Generate encryption key if .env doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "Generating configuration..."
    
    # Copy example env file
    cp .env.example .env
    
    # Generate secret key
    secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Generate encryption key
    encryption_key=$(python3 -m app.security | grep -A 1 "Generated Encryption Key:" | tail -n 1)
    
    # Update .env file
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=$secret_key|" .env
        sed -i '' "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$encryption_key|" .env
    else
        # Linux
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$secret_key|" .env
        sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$encryption_key|" .env
    fi
    
    echo "Configuration file created: .env"
    echo "Secret keys have been generated automatically"
else
    echo ""
    echo ".env file already exists, skipping configuration generation"
fi

# Create logs directory
mkdir -p logs

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "To start the development server:"
echo "  1. Activate the virtual environment:"
echo "     source ../../venv/bin/activate"
echo ""
echo "  2. Run the server:"
echo "     uvicorn app.main:app --reload"
echo ""
echo "  3. Access the API:"
echo "     - API: http://localhost:8000"
echo "     - Docs: http://localhost:8000/api/docs"
echo ""
echo "For more information, see README.md"
echo ""

# Made with Bob
