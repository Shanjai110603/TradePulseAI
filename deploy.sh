#!/usr/bin/env bash
# ==============================================================================
# TradePulse AI - 1-Click Universal Cloud Deployment Script
# Supports: AWS EC2 (t2.micro / t3.micro), Oracle Cloud, DigitalOcean, Ubuntu
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 TradePulse AI - Cloud Server Deployment Starting"
echo "=========================================================="

# 1. Check RAM and automatically configure 2GB Swap for 1GB RAM instances (AWS EC2)
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
echo "🧠 Detected System RAM: ${TOTAL_RAM_MB} MB"

if [ "$TOTAL_RAM_MB" -lt 1500 ]; then
    if [ ! -f /swapfile ]; then
        echo "⚡ Low RAM detected (<= 1GB, standard on AWS Free Tier). Creating 2GB Swapfile..."
        sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
        echo "✅ 2GB Swap configured successfully to prevent OOM errors."
    else
        echo "✅ Swapfile already active."
    fi
fi

# 2. Update system packages
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release iptables ufw

# 3. Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker Engine & Docker Compose Plugin..."
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

# 4. Configure Firewall (Port 80 HTTP, Port 443 HTTPS, Port 8000 API)
echo "🛡️ Configuring Firewall rules (Ports 80, 443, 8000)..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

# 5. Prepare Environment Configuration (.env)
if [ ! -f .env ]; then
    echo "⚙️ Creating production .env file from .env.example..."
    cp .env.example .env
fi

# 6. Build and Launch Containers
echo "🏗️ Building and starting Docker containers..."
sudo docker compose down --remove-orphans 2>/dev/null || true
sudo docker compose up -d --build

# 7. Wait for Database & Backend initialization
echo "⏳ Initializing 24/7 Market Scanner and Database..."
sleep 10

# 8. Print Status
echo ""
echo "=========================================================="
echo "🎉 TradePulse AI is LIVE and Running 24/7!"
echo "=========================================================="
PUBLIC_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
echo "🌐 Web Dashboard: http://${PUBLIC_IP}"
echo "📡 API Endpoint:  http://${PUBLIC_IP}/api/v1"
echo "🤖 Telegram Bot:  Active & Broadcasting (@Logutrader_bot)"
echo "=========================================================="
sudo docker compose ps
