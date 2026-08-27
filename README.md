# 🏆 League of Legends +EV Draft & Match Outcome Prediction Model
### Quantitative Machine Learning, Probability Calibration & Prediction Market Alpha Engine

---

## 📌 Overview & Edge Hypothesis

In esports prediction markets (e.g., **Polymarket**, **SX Bet**, **Betfair**) and sportsbooks:
1. **Pre-match market prices** already reflect historical team quality, public hype, and general standings.
2. **Market Inefficiencies (+EV Alpha)** are concentrated in the **Draft Phase (Picks & Bans)**, where drafting mistakes, champion counter-picks, team composition scaling curves, and full-AD armor vulnerability shift the true underlying win probability beyond what the market has priced in.

This engine decomposes match outcome prediction into a **Two-Stage Quantitative Architecture**:
$$\mathbb{P}(\text{Blue Win}) = \sigma\left( \text{logit}(P_{\text{baseline}}) + \Delta_{\text{draft}} + \beta_{\text{side}} \right)$$

- **$P_{\text{baseline}}$**: Time-decayed dynamic Elo/Glicko-2 team strength rating computed strictly chronologically.
- **$\Delta_{\text{draft}}$**: Pure composition alpha derived from Bayesian regularized lane counters, crowd control (CC) duration, engage range, scaling power curves, and damage profile balance.
- **$\beta_{\text{side}}$**: Dynamic Blue side advantage calibration (~54-56% competitive win rate).

---

## 🚀 Running on Google Colab (Zero Local Resource Usage)

The complete end-to-end training, feature engineering, and backtesting pipeline is packaged into a turnkey Google Colab notebook:

### **[`lol_draft_ev_model_colab.ipynb`](file:///C:/Users/Will%20Palaia/Downloads/dev/LolOutcomePredictFromDraft/lol_draft_ev_model_colab.ipynb)**

### Steps to Run in Cloud:
1. Open [Google Colab](https://colab.research.google.com/).
2. Click **Upload** and select `lol_draft_ev_model_colab.ipynb`.
3. In the menu, go to **Runtime → Run all** (or press `Ctrl + F9`).
4. Google Colab will automatically download multi-season pro match datasets (2022–2025) onto Google's cloud servers, train the models, calibrate probabilities, backtest the +EV betting strategy, and output the interactive draft evaluator.

---

## 🗂️ Project Structure

```text
LolOutcomePredictFromDraft/
├── lol_draft_ev_model_colab.ipynb  # Self-contained Google Colab cloud notebook
├── config/
│   ├── default_config.yaml         # Hyperparameters, ratings, Kelly sizing & EV thresholds
│   └── champion_metadata.json      # Attributes for 169 champions (CC, engage, damage split, scaling)
├── src/
│   ├── ingestion.py                # Multi-year pro match downloader & parser
│   ├── ratings.py                  # Chronological Dynamic Elo / Glicko-2 rating engine
│   ├── features.py                 # Bayesian lane counters & composition feature extractor
│   ├── models/
│   │   ├── base_model.py           # Abstract model interface
│   │   ├── tree_models.py          # CatBoost & LightGBM draft alpha classifiers
│   │   └── calibrator.py           # Isotonic & Platt probability calibrator + ECE metrics
│   ├── backtest/
│   │   ├── market_simulator.py     # Closing line odds simulator with market vig/spread
│   │   └── betting_strategy.py     # +EV trade signal generator & Fractional Kelly backtester
│   └── inference.py                # Live match & draft evaluation CLI
├── run_pipeline.py                 # Local runner (optional)
└── README.md
```

---

## 📊 Mathematical & Backtest Engine

### 1. Bayesian Regularized Lane Counters
To prevent overfitting on low sample size champion matchups:
$$\hat{p}_{\text{matchup}} = \frac{k + \alpha}{n + \alpha + \beta} - 0.50$$
where $\alpha = 10, \beta = 10$ (Empirical Bayes prior towards 50%).

### 2. +EV Trade Execution Trigger
$$\text{Expected Value (EV)} = (P_{\text{model}} \times \text{Decimal Odds}) - 1.0$$
A trade is executed only when $\text{EV} \ge +3\%$.

### 3. Position Sizing via Fractional Kelly Criterion
$$f^* = \min\left( \frac{P_{\text{model}} \times (\text{Odds} - 1) - (1 - P_{\text{model}})}{\text{Odds} - 1} \times 0.25, \; 5\% \text{ bankroll cap} \right)$$

---

## 🎯 Interactive Draft Evaluator Example

In Python or Google Colab:
```python
from src.inference import DraftPredictor

predictor = DraftPredictor()
result = predictor.evaluate_draft(
    blue_team="T1",
    red_team="Gen.G",
    blue_picks={"top": "Rumble", "jng": "Jarvan IV", "mid": "Orianna", "bot": "Kalista", "sup": "Renata Glasc"},
    red_picks={"top": "K'Sante", "jng": "Maokai", "mid": "Azir", "bot": "Zeri", "sup": "Lulu"},
    market_odds_blue=2.10,
    market_odds_red=1.75
)
print(result)
```
