#!/bin/bash

echo "Starting Chen's Engineer Toolbox - Backend API"
echo "=============================================="
echo ""
echo "Starting backend at http://localhost:8000"
echo "API docs will be at http://localhost:8000/docs"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Force polling mode for file watcher (fixes reload on WSL/Docker/Windows)
export WATCHFILES_FORCE_POLLING=True

# Explicitly watch backend dir and subdirs for reliable hot reload
python -m uvicorn backend.main:app --reload --reload-dir backend

# Check if command failed
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to start backend!"
    echo ""
    echo "Please ensure:"
    echo "  1. Python 3.11+ is installed: python --version"
    echo "  2. Dependencies are installed: pip install -r requirements.txt"
    echo "  3. You are in the project root directory"
    echo ""
    read -p "Press Enter to exit..."
fi 