#!/bin/bash
# Hard kill all Tool Box processes (backend port 8000, frontend port 8501)
# Use this when normal Ctrl+C or closing the terminal leaves processes running

echo ""
echo "============================================"
echo " Hard Kill - Chen's Engineer Toolbox"
echo "============================================"
echo ""
echo "Killing processes on ports 8000 (backend) and 8501 (frontend)..."
echo ""

kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti :$port 2>/dev/null)
    if [[ -n "$pids" ]]; then
        echo "Killing PIDs on port $port: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null
    else
        echo "No process found on port $port"
    fi
}

kill_port 8000
kill_port 8501

echo ""
echo "Done. Ports 8000 and 8501 should now be free."
echo "You can restart the app with ./run_backend.sh and ./run_frontend.sh"
echo ""
