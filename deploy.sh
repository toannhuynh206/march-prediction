#!/bin/bash
# Deploy march-prediction to DigitalOcean droplet
# Usage: ./deploy.sh <droplet-ip>
#
# Prerequisites on droplet:
#   sudo apt update && sudo apt install -y python3.12 python3.12-venv git
#
# This script:
#   1. Clones/pulls the repo
#   2. Sets up Python venv
#   3. Installs dependencies
#   4. Initializes the database
#   5. (Future) Starts the web server

set -e

DROPLET_IP="${1:?Usage: ./deploy.sh <droplet-ip>}"
REMOTE_USER="${2:-root}"
APP_DIR="/opt/march-prediction"

echo "Deploying to $REMOTE_USER@$DROPLET_IP..."

ssh "$REMOTE_USER@$DROPLET_IP" bash -s "$APP_DIR" << 'REMOTE_SCRIPT'
APP_DIR="$1"
set -e

# Install Python 3.12 if needed
if ! command -v python3.12 &> /dev/null; then
    echo "Installing Python 3.12..."
    apt update
    apt install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update
    apt install -y python3.12 python3.12-venv python3.12-dev
fi

# Clone or pull
if [ -d "$APP_DIR" ]; then
    echo "Pulling latest..."
    cd "$APP_DIR"
    git pull
else
    echo "Cloning repo..."
    git clone https://github.com/toannhuynh206/march-prediction.git "$APP_DIR"
    cd "$APP_DIR"
fi

# Set up venv
if [ ! -d ".venv" ]; then
    echo "Creating venv..."
    python3.12 -m venv .venv
fi

source .venv/bin/activate
pip install -q numpy

# Initialize database
echo "Initializing database..."
python3 src/database.py

echo ""
echo "Deploy complete!"
echo "Database: $APP_DIR/data/march_madness.db"
echo "Python: $(python3 --version)"
REMOTE_SCRIPT

echo "Done! SSH in with: ssh $REMOTE_USER@$DROPLET_IP"
echo "App directory: $APP_DIR"
