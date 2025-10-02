#!/bin/bash

echo "Starting Chen's Engineer Toolbox - Frontend UI"
echo "=============================================="
echo ""

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv to run frontend..."
    uv run streamlit run frontend/Home.py
else
    echo "Using streamlit directly..."
    streamlit run frontend/Home.py
fi 