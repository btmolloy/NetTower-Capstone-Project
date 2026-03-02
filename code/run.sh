#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Environment variables
export NETTOWER_INTERFACE="en0"
export NETTOWER_DISCOVERY_INTERVAL=15
export NETTOWER_MONGO_URI="mongodb://localhost:27017"
export NETTOWER_MONGO_DB_NAME="nettower"
export NETTOWER_ENABLE_PASSIVE_LISTENER=true
export NETTOWER_ENABLE_ACTIVE_DISCOVERY=true
export NETTOWER_DISCOVERY_TARGET_CIDR="192.168.1.0/24"

# Run backend
sudo venv/bin/python -m backEnd.main