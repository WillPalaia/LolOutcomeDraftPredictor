"""
CLI Master Runner for LoL Draft +EV Autonomous Trading Bot.
"""
import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("BotRunner")

from src.bot.bot_engine import DraftBotEngine

def main():
    parser = argparse.ArgumentParser(description="League of Legends +EV Autonomous Draft Trading Bot")
    parser.add_argument("--config", default="config/bot_config.yaml", help="Path to bot configuration YAML")
    parser.add_argument("--test-discord", action="store_true", help="Send a test trade alert to Discord webhook")
    parser.add_argument("--simulate-match", action="store_true", help="Simulate a live match draft evaluation and trigger trade")
    parser.add_argument("--status", action="store_true", help="Display current paper trading portfolio status and stats")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between schedule/match poll cycles")
    
    args = parser.parse_args()
    engine = DraftBotEngine(config_path=args.config)
    
    if args.test_discord:
        print("\n=======================================================")
        print("  TESTING DISCORD WEBHOOK INTEGRATION                  ")
        print("=======================================================")
        if not engine.notifier.is_configured():
            print("❌ Discord webhook URL is not configured!")
            print("Set DISCORD_WEBHOOK_URL in your environment or in config/bot_config.yaml")
            return
            
        print(f"Sending test +EV Trade Alert to Discord...")
        mock_match = engine.listener.generate_mock_live_match(blue_team="T1", red_team="Gen.G", league="LCK")
        engine.process_match(mock_match, is_dry_run=True)
        print("✅ Test trade signal sent! Check your Discord channel.")
        return
        
    if args.status:
        summary = engine.portfolio.get_portfolio_summary()
        print("\n=======================================================")
        print("  PAPER TRADING PORTFOLIO SUMMARY                     ")
        print("=======================================================")
        print(f"  Current Bankroll:    ${summary['bankroll']:,.2f}")
        print(f"  Peak Bankroll:       ${summary['peak_bankroll']:,.2f}")
        print(f"  Total Wagered:       ${summary['total_wagered']:,.2f}")
        print(f"  Net Profit:          ${summary['total_profit']:,.2f}")
        print(f"  Total Bets Placed:   {summary['total_bets']}")
        print(f"  Win Rate:            {summary['win_rate']:.2f}%")
        print(f"  Return on Inv (ROI): {summary['roi']:.2f}%")
        print(f"  Max Drawdown:        {summary['max_drawdown_pct']:.2f}%")
        print(f"  Today's PnL:         {summary['daily_pnl_pct']:+.2f}%")
        print("=======================================================\n")
        return
        
    if args.simulate_match:
        print("\n[SIMULATION] Processing live draft match event: T1 vs Gen.G...")
        mock_match = engine.listener.generate_mock_live_match(blue_team="T1", red_team="Gen.G", league="LCK")
        engine.process_match(mock_match, is_dry_run=True)
        print("Done!")
        return

    # Start 24/7 autonomous daemon
    engine.run_daemon(poll_interval_seconds=args.poll_interval)

if __name__ == "__main__":
    main()
