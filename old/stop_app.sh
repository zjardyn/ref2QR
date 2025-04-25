#!/bin/bash

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping Ref2QR Application...${NC}"

# Find Flask processes more reliably
# Look for any Python process running flask
PIDS=$(ps aux | grep "[p]ython -m flask" | awk '{print $2}')

if [ -z "$PIDS" ]; then
    # Try another approach - look for app.py
    PIDS=$(ps aux | grep "[a]pp.py" | awk '{print $2}')
fi

if [ -z "$PIDS" ]; then
    echo -e "${RED}No running Flask application found${NC}"
    exit 1
else
    for PID in $PIDS; do
        echo -e "${GREEN}Found Flask application running with PID: $PID${NC}"
        kill $PID
        echo -e "${GREEN}Sent kill signal to PID: $PID${NC}"
    done
    
    echo -e "${GREEN}All Flask applications should be stopped. Waiting to confirm...${NC}"
    sleep 2
    
    # Check if processes are still running
    REMAINING=$(ps aux | grep "[p]ython -m flask" | wc -l)
    
    if [ $REMAINING -gt 0 ]; then
        echo -e "${RED}Some processes might still be running. Using force kill...${NC}"
        # Try to force kill
        ps aux | grep "[p]ython -m flask" | awk '{print $2}' | xargs kill -9 2>/dev/null
        echo -e "${GREEN}Force kill attempted.${NC}"
    else
        echo -e "${GREEN}All Flask applications stopped successfully${NC}"
    fi
fi 