#!/bin/bash
# Build script for Render deployment
# This script runs during the build phase

echo "🚀 Starting Render build process..."

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Create output directory
mkdir -p /tmp/output

# Verify installation
echo "✅ Verifying installation..."
python -c "import aiohttp, redis, psycopg2, selectolax; print('All dependencies installed successfully')"

echo "🎉 Build completed successfully!"