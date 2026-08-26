# ☁️ AWS EC2 Complete 24/7 Deployment Guide

This guide walks you step-by-step through deploying **TradePulse AI** on an **AWS EC2 instance** (`t2.micro` or `t3.micro` - **100% Free for 12 months** on AWS Free Tier).

---

## 🛠️ Step 1: Launch an AWS EC2 Instance

1. Log into your **[AWS Management Console](https://console.aws.amazon.com)**.
2. In the search bar, type **EC2** and click **EC2**.
3. Click the orange **Launch Instance** button.
4. Fill in the following settings:
   * **Name**: `tradepulse-bot`
   * **Application and OS Images**: Choose **Ubuntu** (select **Ubuntu Server 24.04 LTS (HVM)**).
   * **Instance Type**: Select **`t2.micro`** or **`t3.micro`** (Free tier eligible).
   * **Key Pair (login)**:
     * Click *Create new key pair*.
     * Name: `tradepulse-key`.
     * Type: `RSA`, format `.pem` (or `.ppk` if using PuTTY).
     * Click *Create key pair* and save the downloaded file.
   * **Network Settings (Firewall)**:
     * ✅ **Allow SSH traffic from**: `Anywhere (0.0.0.0/0)`
     * ✅ **Allow HTTP traffic from the internet**: Checked
     * ✅ **Allow HTTPS traffic from the internet**: Checked
   * **Configure Storage**: Default `8 GiB` or set to `20 GiB` gp3 (up to 30 GB is free).
5. Click **Launch Instance**.
6. Wait 30 seconds, click **Instances**, and copy your **Public IPv4 address** (e.g. `54.210.xx.xx`).

---

## 💻 Step 2: Connect to Your AWS Server

Open PowerShell or Terminal on your computer and run:

```bash
# 1. Set permissions on your key (Mac/Linux only)
chmod 400 tradepulse-key.pem

# 2. Connect to the instance
ssh -i "tradepulse-key.pem" ubuntu@<YOUR_AWS_PUBLIC_IP>
```

---

## 🚀 Step 3: Run 1-Click Deployment

Once connected to your AWS server, run:

```bash
# 1. Clone the repository
git clone https://github.com/logeshpythonbot-crypto/TradePulse-AI-.git
cd TradePulse-AI-

# 2. Make executable and run deployment script
chmod +x deploy.sh
./deploy.sh
```

### What `deploy.sh` Does Automatically:
* 🧠 **Sets up 2GB Swap Memory**: Guarantees fast builds on 1GB RAM instances.
* 🐳 **Installs Docker & Docker Compose**.
* 🛡️ **Configures Linux Firewalls**.
* 🚀 **Launches PostgreSQL, FastAPI Backend, 24/7 Scanner & Nginx Frontend**.

---

## 🌐 Step 4: Access Your Live System

Once the script finishes:
* **Web Dashboard**: `http://<YOUR_AWS_PUBLIC_IP>`
* **API Documentation**: `http://<YOUR_AWS_PUBLIC_IP>/api/v1/docs`
* **Telegram Bot**: Open **`@Logutrader_bot`** in Telegram and send `/start` or `/signal`!

---

## 🔧 Useful AWS Maintenance Commands

* **Check Live Logs**:
  ```bash
  sudo docker compose logs -f backend
  ```
* **Restart Services**:
  ```bash
  sudo docker compose restart
  ```
* **Update Code from GitHub**:
  ```bash
  git pull origin main
  sudo docker compose up -d --build
  ```
