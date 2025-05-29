#!/bin/bash

# Get the maintenance key from environment variable
MAINTENANCE_KEY=${MAINTENANCE_KEY:-"your_default_key_here"}

# Make the HTTP request to the cleanup endpoint
curl -s "http://localhost:5000/maintenance/cleanup?key=$MAINTENANCE_KEY" 