"""
+EV Value Betting Engine & Fractional Kelly Bankroll Backtester.
"""
import numpy as np
import pandas as pd
from typing import Dict, List

class EVBettingBacktester:
    """
    Executes historical backtesting of the model against market lines using Kelly sizing.
    """
    def __init__(self, 
                 initial_bankroll: float = 10000.0, 
                 ev_threshold: float = 0.03, 
                 kelly_fraction: float = 0.25,
                 max_bet_fraction: float = 0.05):
        self.initial_bankroll = initial_bankroll
        self.ev_threshold = ev_threshold
        self.kelly_fraction = kelly_fraction
        self.max_bet_fraction = max_bet_fraction

    def calculate_kelly_stake(self, p_win: float, decimal_odds: float, bankroll: float) -> float:
        """
        Calculate Fractional Kelly stake:
        f* = (p * (b + 1) - 1) / b, where b = decimal_odds - 1
        """
        b = decimal_odds - 1.0
        if b <= 0:
            return 0.0
            
        full_kelly = (p_win * (b + 1.0) - 1.0) / b
        if full_kelly <= 0:
            return 0.0
            
        stake_pct = min(full_kelly * self.kelly_fraction, self.max_bet_fraction)
        return float(stake_pct * bankroll)

    def run_backtest(self, df_results: pd.DataFrame) -> Dict:
        """
        Run complete chronological betting simulation.
        Required columns in df_results:
          ['blue_win', 'calibrated_blue_prob', 'odds_blue', 'odds_red']
        """
        bankroll = self.initial_bankroll
        bankroll_history = [bankroll]
        trades = []
        
        total_bets = 0
        winning_bets = 0
        total_wagered = 0.0
        total_profit = 0.0
        
        for idx, row in df_results.iterrows():
            p_blue = float(row['calibrated_blue_prob'])
            p_red = 1.0 - p_blue
            actual_blue_win = int(row['blue_win'])
            
            odds_blue = float(row['odds_blue'])
            odds_red = float(row['odds_red'])
            
            # Expected Value
            # EV = (P * Odds) - 1
            ev_blue = (p_blue * odds_blue) - 1.0
            ev_red = (p_red * odds_red) - 1.0
            
            bet_placed = False
            side = None
            stake = 0.0
            win = False
            profit = 0.0
            
            # Trigger trade if EV threshold exceeded
            if ev_blue >= self.ev_threshold and ev_blue >= ev_red:
                side = "Blue"
                stake = self.calculate_kelly_stake(p_blue, odds_blue, bankroll)
                if stake > 0:
                    bet_placed = True
                    total_bets += 1
                    total_wagered += stake
                    if actual_blue_win == 1:
                        win = True
                        winning_bets += 1
                        profit = stake * (odds_blue - 1.0)
                    else:
                        profit = -stake
                        
            elif ev_red >= self.ev_threshold:
                side = "Red"
                stake = self.calculate_kelly_stake(p_red, odds_red, bankroll)
                if stake > 0:
                    bet_placed = True
                    total_bets += 1
                    total_wagered += stake
                    if actual_blue_win == 0:
                        win = True
                        winning_bets += 1
                        profit = stake * (odds_red - 1.0)
                    else:
                        profit = -stake
                        
            if bet_placed:
                bankroll += profit
                total_profit += profit
                bankroll_history.append(bankroll)
                trades.append({
                    "game_idx": idx,
                    "side": side,
                    "ev": ev_blue if side == "Blue" else ev_red,
                    "stake": round(stake, 2),
                    "profit": round(profit, 2),
                    "bankroll": round(bankroll, 2),
                    "win": win
                })
                
        # Performance analytics
        df_trades = pd.DataFrame(trades)
        roi = (total_profit / total_wagered * 100.0) if total_wagered > 0 else 0.0
        win_rate = (winning_bets / total_bets * 100.0) if total_bets > 0 else 0.0
        
        # Max Drawdown
        b_series = pd.Series(bankroll_history)
        running_max = b_series.cummax()
        drawdown = (b_series - running_max) / running_max
        max_drawdown = float(drawdown.min() * 100.0)
        
        # Sharpe Ratio (annualized approx)
        if len(df_trades) > 1 and df_trades['profit'].std() > 0:
            sharpe = float((df_trades['profit'].mean() / df_trades['profit'].std()) * np.sqrt(250))
        else:
            sharpe = 0.0

        return {
            "initial_bankroll": self.initial_bankroll,
            "final_bankroll": round(bankroll, 2),
            "total_profit": round(total_profit, 2),
            "total_bets": total_bets,
            "winning_bets": winning_bets,
            "win_rate_pct": round(win_rate, 2),
            "total_wagered": round(total_wagered, 2),
            "roi_pct": round(roi, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "trades": df_trades
        }
