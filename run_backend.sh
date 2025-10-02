#!/bin/bash

echo "Starting Chen's Engineer Toolbox - Backend API"
echo "=============================================="
echo ""

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv to run backend..."
    uv run uvicorn backend.main:app --reload
else
    echo "Using uvicorn directly..."
    uvicorn backend.main:app --reload
fi 