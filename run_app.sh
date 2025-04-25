#!/bin/bash

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Ref2QR Application...${NC}"

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}No virtual environment found, using system Python${NC}"
fi

# Check if Flask is installed
python -c "import flask" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}Flask is not installed. Installing required packages...${NC}"
    pip install -r requirements.txt
fi

# Check for database file and create if it doesn't exist
echo -e "${YELLOW}Checking database...${NC}"

# Run the Flask application
echo -e "${GREEN}Starting server...${NC}"
echo -e "${GREEN}Access the application at: ${YELLOW}http://localhost:5000${NC}"
echo -e "${GREEN}Press Ctrl+C to stop the server${NC}"

# Run in development mode
export FLASK_APP=app.py
export FLASK_ENV=development
python -m flask run --host=0.0.0.0 