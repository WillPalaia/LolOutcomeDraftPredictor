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
        Sends rich trade signal embed for a detected +EV opportunity.
        """
        p_target = p_final_blue if recommended_side == "Blue" else (1.0 - p_final_blue)
        odds_target = market_odds_blue if recommended_side == "Blue" else market_odds_red
        ev_target = ev_blue if recommended_side == "Blue" else ev_red
        target_team = blue_team if recommended_side == "Blue" else red_team
        
        b_picks_str = f"🛡️ **Top:** {blue_picks.get('top', '-')}\n🌿 **Jng:** {blue_picks.get('jng', '-')}\n⚡ **Mid:** {blue_picks.get('mid', '-')}\n🏹 **Bot:** {blue_picks.get('bot', '-')}\n💖 **Sup:** {blue_picks.get('sup', '-')}"
        r_picks_str = f"🛡️ **Top:** {red_picks.get('top', '-')}\n🌿 **Jng:** {red_picks.get('jng', '-')}\n⚡ **Mid:** {red_picks.get('mid', '-')}\n🏹 **Bot:** {red_picks.get('bot', '-')}\n💖 **Sup:** {red_picks.get('sup', '-')}"
        
        status_tag = "🧪 [PAPER TRADE / DRY RUN]" if is_dry_run else "🚨 [LIVE TRADE EXECUTED]"
        color = 0x00FF7F if recommended_side == "Blue" else 0xFF4500 # SpringGreen for Blue, OrangeRed for Red
        
        embed = {
            "title": f"{status_tag} +EV Trade Signal on {target_team}!",
            "description": f"**League:** `{league.upper()}` | **Match:** `{blue_team} (Blue)` vs `{red_team} (Red)`\n**Action:** Placed **${stake_usd:,.2f}** on **{target_team}** @ `{odds_target:.2f}` odds ({stake_usd/bankroll*100:.1f}% of Bankroll)",
            "color": color,
            "fields": [
                {
                    "name": "📊 Model Quantitative Edge",
                    "value": (
                        f"• **Target Team:** `{target_team}` ({recommended_side} Side)\n"
                        f"• **True Win Prob:** `{p_target*100:.1f}%`\n"
                        f"• **Market Implied:** `{(1.0/odds_target)*100:.1f}%` (Odds: `{odds_target:.2f}`)\n"
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
                    "name": "💼 Current Portfolio State",
                    "value": f"• **Total Bankroll:** `${bankroll:,.2f}`\n• **Allocated Stake:** `${stake_usd:,.2f}`",
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
        Sends settlement update when a match concludes.
        """
        is_win = (profit > 0)
        color = 0x2ECC71 if is_win else 0xE74C3C # Green for win, Red for loss
        emoji = "🎉 PROFIT SETTLED" if is_win else "📉 LOSS RECORDED"
        target_team = blue_team if side_bet == "Blue" else red_team
        
        embed = {
            "title": f"{emoji}: {target_team} ({side_bet})",
            "description": f"**Match:** `{blue_team}` vs `{red_team}` ({league.upper()})\n**Winner:** `{winner}`",
            "color": color,
            "fields": [
                {
                    "name": "Result Details",
                    "value": (
                        f"• **Wagered:** `${stake:,.2f}` on `{target_team}`\n"
                        f"• **PnL:** `{'+$' if is_win else '-$'}{abs(profit):,.2f}`\n"
                        f"• **New Bankroll:** `${bankroll:,.2f}`"
                    ),
                    "inline": True
                },
                {
                    "name": "Portfolio Statistics",
                    "value": (
                        f"• **Total Settled Trades:** `{total_trades}`\n"
                        f"• **Win Rate:** `{win_rate:.1f}%`"
                    ),
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Match ID: {match_id}"
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return self.send_embed(embed)

    def send_system_status(self, title: str, message: str, color: int = 0x3498DB) -> bool:
        """
        Sends general bot operational status or heartbeat message.
        """
        embed = {
            "title": f"🤖 {title}",
            "description": message,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return self.send_embed(embed)
