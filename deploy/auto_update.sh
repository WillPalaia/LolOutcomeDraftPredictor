#!/usr/bin/env bash
# =============================================================================
# 🔄 Autonomous Git Auto-Updater for LoL Draft Bot VPS
# Automatically checks for remote git updates on main, pulls them, and restarts the service.
# Can be run via cron (e.g., every 5 minutes: */5 * * * * /path/to/auto_update.sh)
# =============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Fetch latest commits without merging
git fetch origin main > /dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 New changes detected on origin/main. Updating..."
    git pull origin main
    
    # Update dependencies if requirements changed
    if [ -f "venv/bin/pip" ]; then
        venv/bin/pip install -r requirements.txt --quiet
    fi
    
    # Restart the systemd bot service
    if systemctl is-active --quiet lol-draft-bot.service; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 Restarting lol-draft-bot.service..."
        sudo systemctl restart lol-draft-bot.service
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Updated to commit $(git rev-parse --short HEAD) successfully!"
fi
