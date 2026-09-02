# 🧠 Session Context & Project State: LoL +EV Draft Prediction & Trading Bot

**Last Updated:** August 30, 2026  
**Workspace:** `C:\Users\Will Palaia\Downloads\dev\LolOutcomePredictFromDraft`

---

## 📌 1. Project Objective & Core Mathematical Model

Build a quantitative machine learning and +EV betting engine for League of Legends esports prediction markets (Polymarket, SX Bet, Betfair, sportsbooks).

$$\mathbb{P}(\text{Blue Win}) = \text{clip}\left(P_{\text{baseline}} + \Delta_{\text{draft}}, \; 0.03, \; 0.97\right)$$

- **$P_{\text{baseline}}$**: Dynamic chronological Elo/Glicko-2 team rating with Blue side bias (~54–56% win rate).
- **$\Delta_{\text{draft}}$**: Regularized residual composition alpha derived from CatBoost regressing on $(y - P_{\text{baseline}})$, bounded to $[-0.08, +0.08]$.
- **Heavy Patch Weighting**: Sample weighting $w_i = \exp(-0.06 \cdot \Delta\text{patch}) \times (1.0 + 3.0 \cdot \mathbb{I}(p_i = P_{\text{current}}))$ prioritizing the active tournament patch (4x multiplier) while preserving historical sample size to prevent overfitting.
- **Decision Hurdle**: Trade executed only when $\text{Expected Value (EV)} \ge +2.5\%$.
- **Risk Management**: 1/5th Fractional Kelly Criterion with a **3.5% maximum stake cap** and **10% daily stop-loss circuit breaker**.
- **Execution Timing & Messaging**: Zero spam; Discord webhook notifications sent **ONLY when an actual bet is placed** right at the exact time when draft is finalized and the game hasn't started yet (pre-game post-draft window).

---

## 🗂️ 2. Repository & File Structure

```text
LolOutcomePredictFromDraft/
├── context.md                         # Handover & state context file
├── README.md                          # Full architectural overview & mathematical guide
├── antigravity_agent_instructions.md  # Original prompt specifications
├── lol_draft_ev_model_colab.ipynb     # Self-contained Google Colab cloud training notebook
├── run_pipeline.py                    # Local master training & evaluation pipeline
├── run_bot.py                         # 24/7 Autonomous Bot Daemon CLI runner
├── live_draft_cli.py                  # Interactive live stream CLI evaluator
├── requirements.txt                   # VPS & local Python dependencies
├── config/
│   ├── default_config.yaml            # Model hyperparameters, patch weights & ratings settings
│   ├── champion_metadata.json         # Kit attributes for 169 champions (CC, engage, scaling)
│   └── bot_config.yaml                # 24/7 bot risk parameters, poll intervals & leagues
├── data/
│   ├── raw/                           # Oracle's Elixir multi-season match CSVs (2024 pro data)
│   ├── processed/                     # Feature matrices and rating tables
│   ├── cache/                         # Serialized models and backtest summaries
│   ├── bot/                           # SQLite paper portfolio database (paper_portfolio.db)
│   └── screenshots/                   # Live captured stream drafts (live_draft.png)
├── src/
│   ├── ingestion.py                   # Multi-year pro match downloader & parser
│   ├── ratings.py                     # Dynamic Elo rating engine with inter-split decay
│   ├── features.py                    # Bayesian lane counters, patch meta priority & composition feature extractor
│   ├── screen_capture.py              # Desktop & multi-monitor screen grabber (mss)
│   ├── vision_draft.py                # Multimodal draft parser & evaluator bridge
│   ├── models/
│   │   ├── base_model.py              # Abstract model class
│   │   ├── tree_models.py             # Regularized residual CatBoostRegressor with patch sample weighting
│   │   └── calibrator.py              # Isotonic & Platt probability calibrator
│   ├── backtest/
│   │   ├── market_simulator.py        # Bookmaker closing line simulator with vig
│   │   └── betting_strategy.py        # +EV signal backtester with Fractional Kelly
│   └── bot/
│       ├── discord_notifier.py        # Clear bets-only Discord webhook embed engine (Team A vs Team B)
│       ├── paper_trader.py            # SQLite portfolio tracker & daily circuit breaker
│       ├── live_feed_listener.py      # Riot LoL Esports gateway live poller & draft completion detector
│       └── bot_engine.py              # 24/7 autonomous draft evaluator & pre-game bet placement loop
└── deploy/
    ├── README_VPS_DEPLOYMENT.md       # Step-by-step Oracle Cloud Free Tier VPS guide
    ├── setup_vps.sh                   # 1-Click automated Linux setup script
    ├── lol-draft-bot.service          # Linux systemd service for 24/7 auto-restart
    ├── Dockerfile                     # Docker container definition
    └── docker-compose.yml             # Docker Compose orchestration
```

---

## 🛠️ 3. Key Accomplishments This Session

1. **Fixed Discord Messaging System & Root Cause of Missing Messages:**
   - **Root Cause Identified**: The previously configured Riot endpoint `/persisted/val/` with an expired API key was returning `403 Forbidden`, causing `fetch_live_schedule()` to silently return empty results.
   - **Endpoint & Key Overhaul**: Migrated to the active Riot gateway `/persisted/gw/` with dynamic gateway authorization.
   - **Strictly Bets-Only Notifications**: Rebuilt `discord_notifier.py` and `bot_engine.py` to suppress startup status messages, heartbeats, and PASS evaluations. A Discord message is sent **only if a bet is actually placed**.
   - **Explicit Match Formatting**: Alerts clearly state **what team it bet on vs who** (e.g. `[PAPER BET PLACED] T1 vs Gen.G (LCK)`), including exact wager amount, decimal odds, +EV edge %, model probability, and the 10 locked champions.
   - **Exact Execution Timing**: Draft evaluation and bet execution trigger strictly when all 10 picks are locked and the match is in the pre-game window before active rift start.

2. **Heavy Patch Weighting & Meta Priority Engineering:**
   - Implemented `parse_patch_to_num` and `diff_patch_meta_priority` (rolling pick/ban tier presence on that specific patch).
   - Applied exponential patch recency sample weighting ($w_i = \exp(-0.06 \cdot \Delta\text{patch}) \times (1.0 + 3.0 \cdot \mathbb{I}(p_i = P_{\text{current}}))$), assigning a **4x weight multiplier** to current patch matches in training loss.
   - Regularized player mastery priors (`prior=10.0`) to avoid small-sample volatility while balancing composition traits.

3. **Extensive Overfitting Diagnostics & Backtesting:**
   - Evaluated on 8,804 professional 2024 matches across 6 rolling patch time-series splits (14.01 through 14.23).
   - Out-of-sample test results:
     - Accuracy: Train 65.33% vs Test 61.39% (stable gap ~3.9%).
     - ROC-AUC: Train 0.7212 vs Test 0.6339.
     - Out-of-sample +EV Backtest: **279 bets placed, +$1,319.07 Net Profit (+4.87% ROI), Max Drawdown -12.93%, Sharpe Ratio 0.70**.

---

## 🚀 4. Immediate Next Steps

1. **Verify VPS Deployment**:
   - Run `run_bot.py` or restart `systemd` service on VPS.
   - Confirm `DISCORD_WEBHOOK_URL` in `.env` triggers cleanly on live LCK/LPL/LEC/LCS matches.
2. **Monitor Live Paper Trades**:
   - Verify paper portfolio accumulation via `python run_bot.py --status`.

