#!/bin/bash
# =============================================================================
# Digital Ocean Server Setup Script for Promo Pipeline
# =============================================================================
#
# This script sets up everything needed to run the promo pipeline on a fresh
# Ubuntu 22.04 droplet.
#
# Usage:
#   1. Create a new Digital Ocean droplet (Ubuntu 22.04, 2GB RAM minimum)
#   2. SSH into the droplet: ssh root@your-droplet-ip
#   3. Upload your project: scp -r /path/to/project root@your-droplet-ip:/opt/promo-pipeline
#   4. Run this script: bash /opt/promo-pipeline/email_trigger/deployment/setup-server.sh
#
# =============================================================================

set -e  # Exit on error

echo "=========================================="
echo "Promo Pipeline Server Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

PROJECT_DIR="/opt/promo-pipeline"

# Verify project exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project not found at $PROJECT_DIR"
    echo "Please upload your project first:"
    echo "  scp -r /path/to/project root@your-droplet-ip:/opt/promo-pipeline"
    exit 1
fi

echo "[1/7] Updating system packages..."
apt update && apt upgrade -y

echo "[2/7] Installing Python and Node.js..."
apt install -y python3-pip python3-venv nodejs npm git curl wget

# Install Node.js 18+ for Next.js
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

echo "[3/7] Installing Chrome for browser automation..."
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt update && apt install -y google-chrome-stable

echo "[4/7] Setting up Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[5/7] Setting up dashboard..."
cd "$PROJECT_DIR/frontend"
npm install
npm run build

echo "[6/7] Installing systemd services..."
cp "$PROJECT_DIR/email_trigger/deployment/email-watcher.service" /etc/systemd/system/
cp "$PROJECT_DIR/email_trigger/deployment/dashboard.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable email-watcher dashboard

echo "[7/7] Installing Nginx..."
apt install -y nginx

# Copy nginx config
cp "$PROJECT_DIR/email_trigger/deployment/nginx-dashboard.conf" /etc/nginx/sites-available/dashboard
ln -sf /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default  # Remove default site

# Test nginx config
nginx -t

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Create your .env file:"
echo "   cp $PROJECT_DIR/email_trigger/.env.example $PROJECT_DIR/.env"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "2. Update Nginx server_name in:"
echo "   /etc/nginx/sites-available/dashboard"
echo ""
echo "3. Start the services:"
echo "   systemctl start email-watcher dashboard nginx"
echo ""
echo "4. (Optional) Set up SSL with Let's Encrypt:"
echo "   apt install certbot python3-certbot-nginx"
echo "   certbot --nginx -d your-domain.com"
echo ""
echo "5. Check service status:"
echo "   systemctl status email-watcher"
echo "   systemctl status dashboard"
echo "   journalctl -u email-watcher -f  # Watch logs"
echo ""
echo "=========================================="
