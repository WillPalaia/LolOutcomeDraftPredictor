#!/usr/bin/env bash
# =============================================================================
# 🚀 1-Click VPS Setup Script for LoL Draft +EV Autonomous Bot
# Compatible with Ubuntu 22.04 / 24.04 / Oracle Linux on Oracle Cloud or Hetzner
# =============================================================================

set -e

echo "================================================================="
echo "  STARTING LOL +EV DRAFT TRADING BOT VPS SETUP                   "
echo "================================================================="

# 1. Update system packages
echo "📦 Updating system packages..."
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git curl

# 2. Setup Python Virtual Environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 3. Install requirements
echo "📥 Installing required Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Check for .env file
if [ ! -f .env ]; then
    echo "⚠️ .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "❗ PLEASE EDIT .env AND ADD YOUR DISCORD_WEBHOOK_URL!"
fi

# 5. Setup Systemd Service
echo "⚙️ Configuring Systemd Background Service..."
sed -i "s|/home/ubuntu/LolOutcomePredictFromDraft|$(pwd)|g" deploy/lol-draft-bot.service
sed -i "s|User=ubuntu|User=$(whoami)|g" deploy/lol-draft-bot.service

sudo cp deploy/lol-draft-bot.service /etc/systemd/system/lol-draft-bot.service
sudo systemctl daemon-reload
sudo systemctl enable lol-draft-bot.service
sudo systemctl restart lol-draft-bot.service

# 6. Setup Auto-Updater Cron Job (Every 5 minutes)
echo "🔄 Setting up automatic git auto-updater cron job (every 5 minutes)..."
chmod +x deploy/auto_update.sh
AUTO_UPDATE_PATH="$(pwd)/deploy/auto_update.sh"
mkdir -p data/bot
(crontab -l 2>/dev/null | grep -v "auto_update.sh"; echo "*/5 * * * * $AUTO_UPDATE_PATH >> $(pwd)/data/bot/auto_update.log 2>&1") | crontab -

echo "================================================================="
echo "✅ BOT DEPLOYED, RUNNING 24/7, AND AUTO-UPDATING EVERY 5 MINUTES!"
echo "================================================================="
echo "Useful commands:"
echo "  • View Live Bot Logs:   sudo journalctl -u lol-draft-bot.service -f"
echo "  • Check Service Status: sudo systemctl status lol-draft-bot.service"
echo "  • Restart Bot:          sudo systemctl restart lol-draft-bot.service"
echo "  • Check Portfolio:      ./venv/bin/python run_bot.py --status"
echo "  • Check Auto-Updater:   tail -f data/bot/auto_update.log"
echo "================================================================="
