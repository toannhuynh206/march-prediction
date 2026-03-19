#!/bin/bash
# Deploy March Madness to Digital Ocean (ctgDroplet)
# Usage: ./deploy.sh <droplet-ip>

set -e

DROPLET_IP="${1:?Usage: ./deploy.sh <droplet-ip>}"
REMOTE_USER="${2:-root}"
APP_DIR="/opt/march-prediction"
FRONTEND_DIR="/var/www/marchmadness/dist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== March Madness Deploy ==="
echo "Target: $REMOTE_USER@$DROPLET_IP"
echo ""

# Step 1: Build frontend locally
echo "[1/5] Building frontend..."
cd "$SCRIPT_DIR/frontend/app"
npm ci --silent 2>/dev/null
npm run build
cd "$SCRIPT_DIR"

# Step 2: Sync app files to server
echo "[2/5] Syncing app to $APP_DIR..."
rsync -avz --delete \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.env' \
    --exclude '*.pyc' \
    --exclude '.claude' \
    --exclude 'agents' \
    --exclude 'tests' \
    --exclude 'frontend/app/node_modules' \
    "$SCRIPT_DIR/" "$REMOTE_USER@$DROPLET_IP:$APP_DIR/"

# Step 3: Sync frontend dist
echo "[3/5] Syncing frontend dist to $FRONTEND_DIR..."
ssh "$REMOTE_USER@$DROPLET_IP" "mkdir -p $FRONTEND_DIR"
rsync -avz --delete \
    "$SCRIPT_DIR/frontend/app/dist/" "$REMOTE_USER@$DROPLET_IP:$FRONTEND_DIR/"

# Step 4: Set up Nginx + .env
echo "[4/5] Configuring server..."
ssh "$REMOTE_USER@$DROPLET_IP" bash -s "$APP_DIR" << 'REMOTE'
APP_DIR="$1"
cd "$APP_DIR"

# Create .env if missing
if [ ! -f .env ]; then
    cat > .env << 'ENVFILE'
POSTGRES_USER=marchmadness
POSTGRES_PASSWORD=bracketbuster2026
POSTGRES_DB=march_madness
ADMIN_API_KEY=changeme_in_production
TOURNAMENT_YEAR=2026
ENVFILE
    echo "  Created .env — UPDATE passwords before going live!"
fi

# Install Nginx site config if not already there
if [ ! -f /etc/nginx/sites-available/marchmadnesschallenge.store ]; then
    cp "$APP_DIR/nginx/marchmadnesschallenge.store" /etc/nginx/sites-available/
    ln -sf /etc/nginx/sites-available/marchmadnesschallenge.store /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
    echo "  Nginx configured for marchmadnesschallenge.store"
else
    echo "  Nginx config already exists"
fi
REMOTE

# Step 5: Build and start Docker services
echo "[5/5] Starting Docker services..."
ssh "$REMOTE_USER@$DROPLET_IP" bash -s "$APP_DIR" << 'REMOTE'
APP_DIR="$1"
cd "$APP_DIR"

docker compose -f docker-compose.prod.yml build --quiet
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "Waiting for services..."
sleep 5

# Verify
docker compose -f docker-compose.prod.yml ps
echo ""

# Test API health
curl -s http://127.0.0.1:8082/api/health || echo "API not ready yet — check logs: docker compose -f docker-compose.prod.yml logs api"
REMOTE

echo ""
echo "=== Deploy Complete ==="
echo ""
echo "Site: http://marchmadnesschallenge.store"
echo ""
echo "Next steps on the server:"
echo "  1. Update .env passwords: nano $APP_DIR/.env"
echo "  2. SSL: sudo certbot --nginx -d marchmadnesschallenge.store -d www.marchmadnesschallenge.store"
echo "  3. Generate brackets: cd $APP_DIR && docker compose -f docker-compose.prod.yml exec api python3 -m simulation.simulate --all --year 2026 --budget 1000000"
