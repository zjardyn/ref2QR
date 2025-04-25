#!/bin/bash

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Restarting Ref2QR Application...${NC}"

# Kill all Flask processes
echo -e "${YELLOW}Stopping any running Flask processes...${NC}"

# Find all Flask processes
PIDS=$(ps aux | grep "[p]ython -m flask\|[a]pp.py" | awk '{print $2}')

if [ -n "$PIDS" ]; then
    for PID in $PIDS; do
        echo -e "${GREEN}Killing process with PID: $PID${NC}"
        kill -9 $PID 2>/dev/null
    done
    echo -e "${GREEN}All Flask processes killed.${NC}"
    sleep 1
else
    echo -e "${YELLOW}No running Flask processes found.${NC}"
fi

# Start the Flask application
echo -e "${GREEN}Starting server...${NC}"
echo -e "${GREEN}Access the application at: ${YELLOW}http://localhost:5000${NC}"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Start the app in the background
nohup python -m flask --app app.py run --host=0.0.0.0 > flask.log 2>&1 &

echo -e "${GREEN}Application started in background. Output is being logged to flask.log${NC}"
echo -e "${GREEN}Process ID: $!${NC}" 