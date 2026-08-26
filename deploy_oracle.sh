#!/usr/bin/env bash
# ==============================================================================
# TradePulse AI - 1-Click Oracle Cloud Always Free VM Deployment Script
# Supports: Ubuntu 22.04 / 24.04 LTS (ARM64 Ampere A1 & AMD64)
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 TradePulse AI - Oracle Cloud Deployment Starting"
echo "=========================================================="

# 1. Update system packages
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release iptables ufw

# 2. Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker Engine..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "✅ Docker installed successfully."
fi

# 3. Oracle Cloud Firewall Fix (Oracle VM blocks HTTP/HTTPS in iptables by default)
echo "🛡️ Configuring Oracle Cloud Firewall & IPTables..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save 2>/dev/null || true
else
    sudo apt-get install -y iptables-persistent 2>/dev/null || true
fi

# 4. Prepare Environment Configuration (.env)
if [ ! -f .env ]; then
    echo "⚙️ Creating production .env file from .env.example..."
    cp .env.example .env
fi

# 5. Build and Launch Containers
echo "🏗️ Building and starting Docker containers..."
sudo docker compose down --remove-orphans 2>/dev/null || true
sudo docker compose up -d --build

# 6. Wait for Database & Backend to be healthy
echo "⏳ Waiting for services to initialize..."
sleep 10

# 7. Print Status
echo ""
echo "=========================================================="
echo "🎉 TradePulse AI is LIVE on your Oracle Cloud VM!"
echo "=========================================================="
PUBLIC_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
echo "🌐 Web Dashboard: http://${PUBLIC_IP}"
echo "📡 API Endpoint:  http://${PUBLIC_IP}/api/v1"
echo "🤖 Telegram Bot:  Active & Broadcasting (@Logutrader_bot)"
echo "=========================================================="
sudo docker compose ps
