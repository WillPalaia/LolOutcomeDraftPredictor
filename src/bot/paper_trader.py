"""
Persistent Paper Trading Portfolio Manager with SQLite backend.
Tracks open positions, settled trades, daily drawdowns, and portfolio statistics.
"""
import os
import sqlite3
import datetime
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("PaperTrader")

class PaperPortfolio:
    def __init__(self, db_path: str = "data/bot/paper_portfolio.db", initial_bankroll: float = 10000.0):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.initial_bankroll = initial_bankroll
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Portfolio State table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY,
                    bankroll REAL,
                    peak_bankroll REAL,
                    total_wagered REAL,
                    total_profit REAL,
                    winning_bets INTEGER,
                    total_bets INTEGER,
                    daily_start_bankroll REAL,
                    daily_date TEXT
                )
            """)
            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    match_id TEXT,
                    league TEXT,
                    blue_team TEXT,
                    red_team TEXT,
                    side_bet TEXT,
                    odds REAL,
                    model_prob REAL,
                    ev REAL,
                    stake REAL,
                    status TEXT,
                    winner TEXT,
                    profit REAL
                )
            """)
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM portfolio")
            if cursor.fetchone()[0] == 0:
                today = datetime.date.today().isoformat()
                cursor.execute("""
                    INSERT INTO portfolio (
                        id, bankroll, peak_bankroll, total_wagered, total_profit,
                        winning_bets, total_bets, daily_start_bankroll, daily_date
                    ) VALUES (1, ?, ?, 0.0, 0.0, 0, 0, ?, ?)
                """, (self.initial_bankroll, self.initial_bankroll, self.initial_bankroll, today))
                conn.commit()

    def get_portfolio_summary(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT bankroll, peak_bankroll, total_wagered, total_profit, winning_bets, total_bets, daily_start_bankroll, daily_date FROM portfolio WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                return {"bankroll": self.initial_bankroll, "total_profit": 0.0, "total_bets": 0, "win_rate": 0.0, "roi": 0.0}
            
            bankroll, peak, wagered, profit, wins, bets, daily_start, daily_date = row
            
            # Check if new day for daily circuit breaker
            today = datetime.date.today().isoformat()
            if daily_date != today:
                cursor.execute("UPDATE portfolio SET daily_start_bankroll = ?, daily_date = ? WHERE id = 1", (bankroll, today))
                conn.commit()
                daily_start = bankroll
                
            roi = (profit / wagered * 100.0) if wagered > 0 else 0.0
            win_rate = (wins / bets * 100.0) if bets > 0 else 0.0
            drawdown = ((peak - bankroll) / peak * 100.0) if peak > 0 else 0.0
            daily_pnl_pct = ((bankroll - daily_start) / daily_start * 100.0) if daily_start > 0 else 0.0
            
            return {
                "bankroll": bankroll,
                "peak_bankroll": peak,
                "total_wagered": wagered,
                "total_profit": profit,
                "winning_bets": wins,
                "total_bets": bets,
                "win_rate": win_rate,
                "roi": roi,
                "max_drawdown_pct": drawdown,
                "daily_pnl_pct": daily_pnl_pct
            }

    def check_daily_circuit_breaker(self, max_daily_drawdown_pct: float = 10.0) -> bool:
        """
        Returns True if trading is safe; False if daily stop-loss limit is triggered.
        """
        summary = self.get_portfolio_summary()
        if summary["daily_pnl_pct"] <= -max_daily_drawdown_pct:
            logger.critical(f"Circuit breaker active! Daily loss {summary['daily_pnl_pct']:.2f}% exceeds {max_daily_drawdown_pct}%. Trading halted for the day.")
            return False
        return True

    def record_trade(
        self,
        match_id: str,
        league: str,
        blue_team: str,
        red_team: str,
        side_bet: str,
        odds: float,
        model_prob: float,
        ev: float,
        stake: float
    ) -> str:
        trade_id = f"T_{int(datetime.datetime.utcnow().timestamp())}_{match_id}"
        timestamp = datetime.datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, timestamp, match_id, league, blue_team, red_team,
                    side_bet, odds, model_prob, ev, stake, status, winner, profit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', NULL, 0.0)
            """, (trade_id, timestamp, match_id, league, blue_team, red_team, side_bet, odds, model_prob, ev, stake))
            
            # Deduct initial stake from liquid cash
            cursor.execute("UPDATE portfolio SET bankroll = bankroll - ?, total_wagered = total_wagered + ? WHERE id = 1", (stake, stake))
            conn.commit()
            
        logger.info(f"Recorded paper trade {trade_id}: Placed ${stake:,.2f} on {side_bet} @ {odds:.2f} (EV: +{ev*100:.1f}%)")
        return trade_id

    def settle_trade(self, match_id: str, winner_side: str) -> Optional[Dict[str, Any]]:
        """
        Settles open trade for match_id.
        winner_side: 'Blue' or 'Red'
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT trade_id, league, blue_team, red_team, side_bet, odds, stake FROM trades WHERE match_id = ? AND status = 'OPEN'", (match_id,))
            row = cursor.fetchone()
            if not row:
                return None
                
            trade_id, league, b_team, r_team, side_bet, odds, stake = row
            is_win = (side_bet == winner_side)
            profit = (stake * (odds - 1.0)) if is_win else -stake
            returned_cash = (stake * odds) if is_win else 0.0
            
            # Update trade
            cursor.execute("""
                UPDATE trades
                SET status = 'SETTLED', winner = ?, profit = ?
                WHERE trade_id = ?
            """, (winner_side, profit, trade_id))
            
            # Update portfolio
            cursor.execute("""
                UPDATE portfolio
                SET bankroll = bankroll + ?,
                    total_profit = total_profit + ?,
                    winning_bets = winning_bets + ?,
                    total_bets = total_bets + 1,
                    peak_bankroll = MAX(peak_bankroll, bankroll + ?)
                WHERE id = 1
            """, (returned_cash, profit, 1 if is_win else 0, returned_cash))
            conn.commit()
            
        summary = self.get_portfolio_summary()
        return {
            "trade_id": trade_id,
            "match_id": match_id,
            "league": league,
            "blue_team": b_team,
            "red_team": r_team,
            "side_bet": side_bet,
            "winner": winner_side,
            "stake": stake,
            "profit": profit,
            "bankroll": summary["bankroll"],
            "win_rate": summary["win_rate"],
            "total_trades": summary["total_bets"]
        }
