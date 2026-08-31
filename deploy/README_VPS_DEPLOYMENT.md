# 🚀 Step 1 Deployment Guide: Oracle Cloud 24/7 Hosting + Discord Alerts

This guide walks you through deploying the **League of Legends +EV Autonomous Draft Trading Bot** on an **Oracle Cloud Free Tier VPS** ($0/month forever) with **Discord Webhook** mobile notifications.

---

## 1. 📲 Create Your Discord Webhook (2 Minutes)

1. Open **Discord** on desktop/browser.
2. Go to your private server (or create a new private server e.g. *"Esports Alpha Trading"*).
3. Right-click the channel where you want alerts (e.g. `#lol-draft-alerts`) $\to$ **Edit Channel** $\to$ **Integrations** $\to$ **Webhooks**.
4. Click **New Webhook**, name it `LoL Draft Bot`, and click **Copy Webhook URL**.
   * It looks like: `https://discord.com/api/webhooks/123456789/abcdefghijk...`

---

## 2. ☁️ Launch Oracle Cloud Free Instance (5 Minutes)

1. Log into your [Oracle Cloud Console](https://cloud.oracle.com/).
2. Go to **Compute** $\to$ **Instances** $\to$ **Create Instance**.
3. **Settings:**
   * **Name:** `lol-draft-bot-vps`
   * **Image:** `Ubuntu 22.04` or `Ubuntu 24.04` (Canonical Ubuntu)
   * **Shape:** `VM.Standard.A1.Flex` (Ampere ARM, 1-2 OCPU, 6-12 GB RAM - **Always Free**) or `VM.Standard.E2.1.Micro` (AMD, **Always Free**).
   * **Add SSH Keys:** Download the generated Private Key (e.g. `ssh-key.key`).
4. Click **Create** and wait 30 seconds for the **Public IP Address** (e.g. `129.153.xx.xx`).

---

## 3. 💻 Connect to Your VPS via SSH

On your computer (Windows PowerShell, Command Prompt, or Mac/Linux Terminal):

```bash
# Set permissions on your private key (if Mac/Linux: chmod 400 ssh-key.key)
ssh -i path/to/ssh-key.key ubuntu@YOUR_ORACLE_PUBLIC_IP
```

---

## 4. 🚀 Clone & 1-Click Launch Bot

Once inside your VPS terminal:

```bash
# 1. Clone your project repository or copy files
git clone <your_repo_url> LolOutcomePredictFromDraft
cd LolOutcomePredictFromDraft

# 2. Add your Discord Webhook to .env
cp .env.example .env
nano .env
# Paste: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
# Press Ctrl+O (Enter) to save, Ctrl+X to exit.

# 3. Run the 1-Click Setup Script
chmod +x deploy/setup_vps.sh
./deploy/setup_vps.sh
```

---

## 5. 🧪 Verify Your Discord Alerts

Test the Discord alert connection immediately by running:

```bash
./venv/bin/python run_bot.py --test-discord
```
You will immediately receive a color-coded **+EV Trade Signal** embed notification in your Discord channel!

---

## 📊 Useful VPS Management Commands

| Action | Command |
| :--- | :--- |
| **Pull Latest Code & Restart** | `git pull origin main && sudo systemctl restart lol-draft-bot.service` |
| **View Live Bot Logs** | `sudo journalctl -u lol-draft-bot.service -f` |
| **Check Bot Process Status** | `sudo systemctl status lol-draft-bot.service` |
| **Restart Bot Daemon** | `sudo systemctl restart lol-draft-bot.service` |
| **Stop Bot** | `sudo systemctl stop lol-draft-bot.service` |
| **View Portfolio Performance** | `./venv/bin/python run_bot.py --status` |

---

## 🔄 Automatic Auto-Updating (Optional)

If you want the VPS to automatically check for new commits on GitHub and auto-restart without needing to SSH in:

1. Make the auto-updater script executable:
   ```bash
   chmod +x deploy/auto_update.sh
   ```
2. Add a 5-minute cron job:
   ```bash
   (crontab -l 2>/dev/null; echo "*/5 * * * * /home/ubuntu/LolOutcomePredictFromDraft/deploy/auto_update.sh >> /home/ubuntu/auto_update.log 2>&1") | crontab -
   ```

---

## 🛡️ Built-in Safety Features Active

* **Paper Trading Mode (`DRY_RUN=true`):** Simulates every trade and logs exact financial performance without risking real capital.
* **Fractional Kelly Sizing:** 1/5th Kelly with a **3.5% maximum bankroll cap per match**.
* **Daily Stop-Loss Circuit Breaker:** Pauses trading automatically if cumulative daily drawdown exceeds **10%**.
* **Systemd Auto-Restart:** If the VPS reboots or network disconnects, the bot automatically restarts and resumes monitoring.

