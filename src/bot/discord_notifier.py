"""
Discord Webhook Notifier for LoL Draft +EV Trading Bot.
Sends rich, color-coded embed messages for trade signals, settlements, and bot status.
"""
import os
import time
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("DiscordNotifier")

class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        
    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("https://discord.com/api/webhooks/"))

    def send_embed(self, embed: Dict[str, Any], content: Optional[str] = None) -> bool:
        if not self.is_configured():
            logger.warning("Discord webhook URL not configured. Notification skipped.")
            return False
            
        payload = {
            "username": "LoL +EV Draft Bot 🤖",
            "avatar_url": "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/5370.jpg",
            "embeds": [embed]
        }
        if content:
            payload["content"] = content
            
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code in [200, 204]:
                logger.info("Discord notification sent successfully.")
                return True
            else:
                logger.error(f"Discord API returned status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False

    def send_trade_signal(
        self,
        match_id: str,
        league: str,
        blue_team: str,
        red_team: str,
        blue_picks: Dict[str, str],
        red_picks: Dict[str, str],
        p_base_blue: float,
        draft_delta: float,
        p_final_blue: float,
        market_odds_blue: float,
        market_odds_red: float,
        ev_blue: float,
        ev_red: float,
        recommended_side: str,
        stake_usd: float,
        bankroll: float,
        is_dry_run: bool = True
    ) -> bool:
        """
        Sends rich trade signal embed ONLY when an actual bet is placed.
        Explicitly states what team was bet on vs who right at draft completion.
        """
        p_target = p_final_blue if recommended_side == "Blue" else (1.0 - p_final_blue)
        odds_target = market_odds_blue if recommended_side == "Blue" else market_odds_red
        ev_target = ev_blue if recommended_side == "Blue" else ev_red
        target_team = blue_team if recommended_side == "Blue" else red_team
        opposing_team = red_team if recommended_side == "Blue" else blue_team
        stake_pct = (stake_usd / max(1.0, bankroll)) * 100.0
        
        b_picks_str = f"🛡️ **Top:** {blue_picks.get('top', '-')}\n🌿 **Jng:** {blue_picks.get('jng', '-')}\n⚡ **Mid:** {blue_picks.get('mid', '-')}\n🏹 **Bot:** {blue_picks.get('bot', '-')}\n💖 **Sup:** {blue_picks.get('sup', '-')}"
        r_picks_str = f"🛡️ **Top:** {red_picks.get('top', '-')}\n🌿 **Jng:** {red_picks.get('jng', '-')}\n⚡ **Mid:** {red_picks.get('mid', '-')}\n🏹 **Bot:** {red_picks.get('bot', '-')}\n💖 **Sup:** {red_picks.get('sup', '-')}"
        
        status_tag = "🧪 [PAPER BET PLACED]" if is_dry_run else "🚨 [LIVE BET EXECUTED]"
        color = 0x00FF7F if recommended_side == "Blue" else 0xFF4500 # SpringGreen for Blue, OrangeRed for Red
        
        embed = {
            "title": f"{status_tag} {target_team} vs {opposing_team} ({league.upper()})",
            "description": (
                f"**Match:** `{blue_team} (Blue)` vs `{red_team} (Red)` | **League:** `{league.upper()}`\n"
                f"**Action:** 🎯 **Placed ${stake_usd:,.2f} on {target_team}** @ `{odds_target:.2f}` odds\n"
                f"**Timing:** ⏱️ **Draft Finalized (Pre-Game)** — Bet locked before match start."
            ),
            "color": color,
            "fields": [
                {
                    "name": "📊 Bet & Value Details",
                    "value": (
                        f"• **Team Bet On:** `{target_team}` ({recommended_side} Side)\n"
                        f"• **Opponent:** `{opposing_team}`\n"
                        f"• **Wager Stake:** `${stake_usd:,.2f}` ({stake_pct:.1f}% of Bankroll)\n"
                        f"• **Decimal Odds:** `{odds_target:.2f}` (Implied: `{(1.0/odds_target)*100:.1f}%`)\n"
                        f"• **Model Win Probability:** `{p_target*100:.1f}%`\n"
                        f"• **Expected Value (EV):** `+{ev_target*100:.2f}%` 🎯\n"
                        f"• **Draft Shift (Δ):** `{draft_delta*100:+.2f}%`"
                    ),
                    "inline": False
                },
                {
                    "name": f"🔵 {blue_team} (Blue Side)",
                    "value": b_picks_str,
                    "inline": True
                },
                {
                    "name": f"🔴 {red_team} (Red Side)",
                    "value": r_picks_str,
                    "inline": True
                },
                {
                    "name": "💼 Current Bankroll",
                    "value": f"`${bankroll:,.2f}`",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"LoL Esports Quantitative Engine • Match ID: {match_id}"
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        return self.send_embed(embed)

    def send_settlement_update(
        self,
        match_id: str,
        league: str,
        blue_team: str,
        red_team: str,
        side_bet: str,
        winner: str,
        stake: float,
        profit: float,
        bankroll: float,
        win_rate: float,
        total_trades: int
    ) -> bool:
        """
        Sends settlement update only if configured.
        """
        # Suppress settlement spam if user only wants bet placement notifications
        logger.info(f"Match {match_id} settled: {winner} won. Profit: ${profit:,.2f}")
        return True

    def send_error_alert(
        self,
        error_title: str,
        error_details: str,
        error_type: str = "API_ERROR",
        cooldown_seconds: int = 1800
    ) -> bool:
        """
        Sends high-priority error alert to Discord when the bot encounters an API or runtime failure.
        Throttled to avoid webhook spam during prolonged outages.
        """
        if not hasattr(self, "_last_error_times"):
            self._last_error_times = {}

        now = time.time()
        last_sent = self._last_error_times.get(error_type, 0.0)
        if now - last_sent < cooldown_seconds:
            logger.debug(f"Error alert '{error_type}' suppressed by cooldown ({int(now - last_sent)}s / {cooldown_seconds}s).")
            return False

        self._last_error_times[error_type] = now
        logger.warning(f"Dispatching Discord error alert: {error_title}")

        embed = {
            "title": f"⚠️ [BOT ERROR ALERT] {error_title}",
            "description": f"**Status:** Action Required / Monitoring Paused\n**Details:** {error_details}",
            "color": 0xE74C3C, # Bright Red
            "fields": [
                {
                    "name": "🔍 Error Category",
                    "value": f"`{error_type}`",
                    "inline": True
                },
                {
                    "name": "⏱️ Throttling",
                    "value": f"Alerts muted for next `{cooldown_seconds // 60} minutes`",
                    "inline": True
                }
            ],
            "footer": {
                "text": "LoL Draft +EV Autonomous Daemon • Exception Monitor"
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return self.send_embed(embed)

    def send_pass_notification(
        self,
        match_id: str,
        league: str,
        blue_team: str,
        red_team: str,
        blue_picks: Dict[str, str],
        red_picks: Dict[str, str],
        p_final_blue: float,
        market_odds_blue: float,
        market_odds_red: float,
        ev_blue: float,
        ev_red: float,
        ev_threshold: float
    ) -> bool:
        """
        Sends an informational embed when a draft is analyzed but neither team meets the +EV betting threshold.
        """
        color = 0x95A5A6  # Gray
        b_picks_str = f"🛡️ **Top:** {blue_picks.get('top', '-')}\n🌿 **Jng:** {blue_picks.get('jng', '-')}\n⚡ **Mid:** {blue_picks.get('mid', '-')}\n🏹 **Bot:** {blue_picks.get('bot', '-')}\n💖 **Sup:** {blue_picks.get('sup', '-')}"
        r_picks_str = f"🛡️ **Top:** {red_picks.get('top', '-')}\n🌿 **Jng:** {red_picks.get('jng', '-')}\n⚡ **Mid:** {red_picks.get('mid', '-')}\n🏹 **Bot:** {red_picks.get('bot', '-')}\n💖 **Sup:** {red_picks.get('sup', '-')}"

        embed = {
            "title": f"⚖️ [DRAFT EVALUATED — PASS] {blue_team} vs {red_team} ({league.upper()})",
            "description": (
                f"**Match:** `{blue_team} (Blue)` vs `{red_team} (Red)` | **League:** `{league.upper()}`\n"
                f"**Decision:** ✋ **PASS / NO VALUE** (No side has +{ev_threshold*100:.1f}% EV edge)\n"
                f"• **Blue ({blue_team}):** Win: `{p_final_blue*100:.1f}%` | Odds: `{market_odds_blue:.2f}` | EV: `{ev_blue*100:+.2f}%`\n"
                f"• **Red ({red_team}):** Win: `{(1.0-p_final_blue)*100:.1f}%` | Odds: `{market_odds_red:.2f}` | EV: `{ev_red*100:+.2f}%`\n"
                f"• **Status:** Draft analyzed live. Zero risk taken."
            ),
            "color": color,
            "fields": [
                {"name": f"🔵 {blue_team} (Blue Side)", "value": b_picks_str, "inline": True},
                {"name": f"🔴 {red_team} (Red Side)", "value": r_picks_str, "inline": True}
            ],
            "footer": {"text": f"LoL +EV Quantitative Engine • Match ID: {match_id}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return self.send_embed(embed)

    def send_system_status(self, title: str, message: str, color: int = 0x3498DB) -> bool:
        """
        Sends operational status updates and heartbeats to Discord.
        """
        logger.info(f"[SYSTEM STATUS]: {title} - {message}")
        embed = {
            "title": f"🟢 [BOT STATUS] {title}",
            "description": message,
            "color": color,
            "footer": {"text": "LoL Draft +EV Autonomous Daemon • Health Monitor"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return self.send_embed(embed)


