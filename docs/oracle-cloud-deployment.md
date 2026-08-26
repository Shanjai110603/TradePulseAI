# 🏛️ Complete Guide: Deploying TradePulse AI on Oracle Cloud Always Free VM

This guide walks you through deploying **TradePulse AI** 24/7 on **Oracle Cloud Infrastructure (OCI) Always Free Tier** (100% Free Forever, 4 vCPUs, 24 GB RAM, 200 GB SSD).

---

## 📋 What You Will Get
* ⚡ **24/7 Uninterrupted Uptime**: The market scanner runs continuously every 5–10s.
* 🤖 **Telegram Signal Station**: Real-time interactive AI signals via `@Logutrader_bot`.
* 📊 **Fast React Dashboard**: Served via high-performance Nginx.
* 💾 **Persistent PostgreSQL Database**: Zero data loss across restarts.
* 💸 **Cost**: **$0.00 / month forever**.

---

## 🛠️ Step 1: Create an Oracle Cloud Free Account
1. Visit **[cloud.oracle.com](https://cloud.oracle.com)**.
2. Sign up for the **Always Free Tier**.
3. Choose your closest home region.

---

## 🖥️ Step 2: Create Your Ampere A1 Compute Instance
1. In the Oracle Cloud Console, navigate to:
   **Compute** → **Instances** → **Create Instance**.
2. **Name**: `tradepulse-vm`
3. **Image and Shape**:
   * Click **Change Image** → Select **Ubuntu 24.04 LTS (Minimal or Standard)**.
   * Click **Change Shape** → Select **Ampere (ARM)** → **VM.Standard.A1.Flex**.
   * Configure: **4 OCPUs** and **24 GB RAM** (Included in Free Tier).
4. **Networking**:
   * Select *Create new virtual cloud network*.
   * Ensure *Assign a public IPv4 address* is checked **Yes**.
5. **Add SSH Keys**:
   * Download and save your Private Key (`.key`) to your computer.
6. Click **Create**. The instance will be running within 60 seconds. Note down your **Public IP Address**.

---

## 🛡️ Step 3: Open Firewall Ports in Oracle Console
Oracle Virtual Cloud Networks (VCN) block inbound traffic by default.

1. In Oracle Console, go to:
   **Networking** → **Virtual Cloud Networks** → Click your VCN.
2. Click **Security Lists** (Default Security List).
3. Click **Add Ingress Rules**:
   * **Source CIDR**: `0.0.0.0/0`
   * **IP Protocol**: `TCP`
   * **Destination Port Range**: `80, 443, 8000`
   * **Description**: `TradePulse HTTP, HTTPS, API`
4. Click **Add Ingress Rules**.

---

## 🚀 Step 4: 1-Click Deployment on the VM

1. Open your terminal (PowerShell, Command Prompt, or Terminal) and SSH into your VM:
   ```bash
   ssh -i /path/to/your_private_key.key ubuntu@<YOUR_ORACLE_PUBLIC_IP>
   ```

2. Clone your GitHub repository:
   ```bash
   git clone https://github.com/logeshpythonbot-crypto/TradePulse-AI-.git
   cd TradePulse-AI-
   ```

3. Make the automated deployment script executable and run it:
   ```bash
   chmod +x deploy_oracle.sh
   ./deploy_oracle.sh
   ```

---

## 🌐 Step 5: Access Your Platform

Once the script finishes:
* **Web Dashboard**: `http://<YOUR_ORACLE_PUBLIC_IP>`
* **API Documentation**: `http://<YOUR_ORACLE_PUBLIC_IP>/api/v1/docs`
* **Telegram Bot**: Open `@Logutrader_bot` in Telegram and send `/start` or `/signal`!

---

## 🔒 Optional: Add Free Domain & SSL (HTTPS)

If you have a domain or a free DuckDNS/Cloudflare domain:
1. Point an `A record` to `<YOUR_ORACLE_PUBLIC_IP>`.
2. Run Certbot to generate a free SSL certificate:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

---

## 🔧 Useful Management Commands

* **View Live Logs**:
  ```bash
  sudo docker compose logs -f backend
  ```
* **View Telegram Scanner Activity**:
  ```bash
  sudo docker compose logs -f backend | grep "scheduler"
  ```
* **Restart Services**:
  ```bash
  sudo docker compose restart
  ```
* **Update to Latest Code**:
  ```bash
  git pull origin main
  sudo docker compose up -d --build
  ```
