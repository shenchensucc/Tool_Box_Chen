#!/bin/bash

echo "Starting Chen's Engineer Toolbox - Frontend UI"
echo "=============================================="
echo ""
echo "Starting frontend at http://localhost:8501"
echo "The app will open automatically in your browser"
echo ""

# Change to script directory, then to frontend
cd "$(dirname "$0")/frontend"

# Run frontend using python -m (more reliable)
python -m streamlit run Home.py

# Check if command failed
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to start frontend!"
    echo ""
    echo "Please ensure:"
    echo "  1. Python 3.11+ is installed: python --version"
    echo "  2. Streamlit is installed: pip install streamlit"
    echo "  3. You are in the project root directory"
    echo ""
    read -p "Press Enter to exit..."
fi 