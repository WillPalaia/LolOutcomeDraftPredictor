# 🧠 Session Context & Project State: LoL +EV Draft Prediction & Trading Bot

**Last Updated:** August 26, 2026  
**Workspace:** `C:\Users\Will Palaia\Downloads\dev\LolOutcomePredictFromDraft`

---

## 📌 1. Project Objective & Core Mathematical Model

Build a quantitative machine learning and +EV betting engine for League of Legends esports prediction markets (Polymarket, SX Bet, Betfair, sportsbooks).

$$\mathbb{P}(\text{Blue Win}) = \text{clip}\left(P_{\text{baseline}} + \Delta_{\text{draft}}, \; 0.03, \; 0.97\right)$$

- **$P_{\text{baseline}}$**: Dynamic chronological Elo/Glicko-2 team rating with Blue side bias (~54–56% win rate).
- **$\Delta_{\text{draft}}$**: Regularized residual composition alpha derived from CatBoost regressing on $(y - P_{\text{baseline}})$, bounded to $[-0.08, +0.08]$. Features include CC scores, engage range, late-game scaling curve deltas, AD-trap vulnerabilities, and Bayesian-shrunk 1v1 lane matchup win rates.
- **Decision Hurdle**: Trade executed only when $\text{Expected Value (EV)} \ge +3.5\%$.
- **Risk Management**: 1/5th Fractional Kelly Criterion with a **3.5% maximum stake cap** and **10% daily stop-loss circuit breaker**.

---

## 🗂️ 2. Repository & File Structure

```text
LolOutcomePredictFromDraft/
├── context.md                         # This session handover & state file
├── README.md                          # Full architectural overview & mathematical guide
├── antigravity_agent_instructions.md  # Original prompt specifications
├── lol_draft_ev_model_colab.ipynb     # Self-contained Google Colab cloud training notebook
├── run_pipeline.py                    # Local master training & evaluation pipeline
├── run_bot.py                         # 24/7 Autonomous Bot Daemon CLI runner
├── live_draft_cli.py                  # Interactive live stream CLI evaluator
├── requirements.txt                   # VPS & local Python dependencies
├── config/
│   ├── default_config.yaml            # Model hyperparameters & ratings settings
│   ├── champion_metadata.json         # Kit attributes for 169 champions (CC, engage, scaling)
│   └── bot_config.yaml                # 24/7 bot risk parameters, poll intervals & leagues
├── data/
│   ├── raw/                           # Oracle's Elixir multi-season match CSVs (2022-2025)
│   ├── processed/                     # Feature matrices and rating tables
│   ├── cache/                         # Serialized models and backtest summaries
│   ├── bot/                           # SQLite paper portfolio database (paper_portfolio.db)
│   └── screenshots/                   # Live captured stream drafts (live_draft.png)
├── src/
│   ├── ingestion.py                   # Multi-year pro match downloader & parser
│   ├── ratings.py                     # Dynamic Elo rating engine with inter-split decay
│   ├── features.py                    # Bayesian lane counters & composition feature extractor
│   ├── screen_capture.py              # Desktop & multi-monitor screen grabber (mss)
│   ├── vision_draft.py                # Multimodal draft parser & evaluator bridge
│   ├── models/
│   │   ├── base_model.py              # Abstract model class
│   │   ├── tree_models.py             # Regularized residual CatBoostRegressor model
│   │   └── calibrator.py              # Isotonic & Platt probability calibrator
│   ├── backtest/
│   │   ├── market_simulator.py        # Bookmaker closing line simulator with vig
│   │   └── betting_strategy.py        # +EV signal backtester with Fractional Kelly
│   └── bot/
│       ├── discord_notifier.py        # Rich color-coded Discord webhook embed engine
│       ├── paper_trader.py            # SQLite portfolio tracker & daily circuit breaker
│       ├── live_feed_listener.py      # Riot / LoL Esports live schedule & match poller
│       └── bot_engine.py              # 24/7 autonomous draft evaluator & decision loop
└── deploy/
    ├── README_VPS_DEPLOYMENT.md       # Step-by-step Oracle Cloud Free Tier VPS guide
    ├── setup_vps.sh                   # 1-Click automated Linux setup script
    ├── lol-draft-bot.service          # Linux systemd service for 24/7 auto-restart
    ├── Dockerfile                     # Docker container definition
    └── docker-compose.yml             # Docker Compose orchestration
```

---

## 🛠️ 3. Key Accomplishments This Session

1. **Fixed Colab Machine Learning Model (`lol_draft_ev_model_colab.ipynb`):**
   - Diagnosed the LightGBM `init_score` inference bug that previously caused test accuracy to drop to 50.88%.
   - Migrated to **Direct Residual Target Regression** ($\text{Target} = y - P_{\text{baseline}}$) with `CatBoostRegressor`.
   - Guaranteed baseline protection ($62.4\%$ baseline) with strictly regularized draft alpha ($\pm 8\%$).
   - Pruned noisy features down to high-signal structural draft traits.
2. **Automated Vision & Screenshot Workflow:**
   - Created `src/screen_capture.py` using `mss` for high-resolution desktop and multi-monitor screen capture.
   - User only needs to provide market odds (e.g. `55c 45c` or `1.85 2.10`), and the multimodal agent extracts champion picks, lane assignments, and team names visually from the stream.
3. **Implemented Step 1: Autonomous 24/7 Bot & Discord Alert Engine:**
   - `src/bot/discord_notifier.py`: Sends rich color-coded embeds for +EV trade signals, settlements, and bot status.
   - `src/bot/paper_trader.py`: Persistent SQLite tracking for paper bankroll ($10,000 initial), win rate, ROI, PnL, and daily drawdown stop-loss ($10\%$).
   - `src/bot/live_feed_listener.py`: Polls Riot/LoL Esports public match endpoints.
   - `src/bot/bot_engine.py`: 24/7 daemon integrating ingestion, evaluation, risk sizing, and notifications.
   - `deploy/`: Full 1-click Oracle Cloud Free Tier VPS deployment suite with `systemd` auto-restart and `setup_vps.sh`.

---

## 🚀 4. Immediate Next Steps for Next Session

1. **Oracle Cloud VPS Verification:**
   - User sets up their Oracle Cloud Free Tier Ubuntu instance.
   - Run `./deploy/setup_vps.sh` on the VPS.
   - Set `DISCORD_WEBHOOK_URL` in `.env` and verify via `./venv/bin/python run_bot.py --test-discord`.
2. **Live Paper Trading Phase:**
   - Let the bot monitor live pro matches (LCK, LPL, LEC, LCS) and verify trade signals in Discord.
   - Monitor portfolio performance via `./venv/bin/python run_bot.py --status`.
3. **Step 2 & 3 (Live Execution on Polymarket / Sportsbooks):**
   - Connect Polymarket CLOB API (`py-clob-client`) with a small test bankroll ($50–$100) for automated order placement.
