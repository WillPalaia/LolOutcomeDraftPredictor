# Instructions for Antigravity Agent: League of Legends Draft Prediction Model

## Objective
Build a machine learning pipeline that predicts the winning team (Blue or Red) of a League of Legends match based *only* on pre-game data (picks, bans, patch version, and team IDs) to identify value bets on esports bookmakers and peer-to-peer (P2P) platforms.

---

## 1. Project Initialization & Architecture
* **Task:** Binary classification (Target variable: `blue_win` -> `1` if Blue wins, `0` if Red wins).
* **Workspace Setup:** Create a modular Python project structured as follows:
  ```text
  ├── data/                  # Raw and processed datasets
  ├── src/
  │   ├── ingestion.py       # API scraping / CSV parsing
  │   ├── features.py        # Feature engineering & embeddings
  │   ├── train.py           # Model training & hyperparameter tuning
  │   └── inference.py       # Real-time odds evaluator / local API
  └── config.yaml            # Patch versions, hyperparameters, and paths
  ```

---

## 2. Phase 1: Data Acquisition & Preprocessing
* **Action Item:** Write a data ingestion script (`src/ingestion.py`) to parse historical competitive match data. Use public datasets (like Oracle's Elixir CSV dumps) or scrape match details using the Riot Games Match-V5 API endpoints.
* **Required Extracted Columns:**
  * `match_id` (Unique string identifier)
  * `patch` (Float/String, e.g., `"14.10"`)
  * `blue_team_id`, `red_team_id` (Categorical identifiers)
  * `blue_pick_1` through `blue_pick_5`, `red_pick_1` through `red_pick_5` (Champion names or IDs)
  * `blue_ban_1` through `blue_ban_5`, `red_ban_1` through `red_ban_5` (Champion names or IDs)
  * `blue_win` (Integer: `1` or `0`)

---

## 3. Phase 2: Feature Engineering Blueprint
Transform raw categorical columns into a format optimized for mathematical processing:
* **One-Hot Composition Matrix:** Create binary indicators representing champion presence.
  * Vector length = Total number of available champions (~165+).
  * Blue picks assigned `+1`, Red picks assigned `-1`, unpicked assigned `0`.
* **Synergy & Counter Scores:** 
  * Calculate historical win rates for distinct champion pairs on the same team (synergy).
  * Calculate historical win rates for direct role matchups (e.g., Top lane champion A vs. B).
* **Meta & Patch Clustering:** Group rows by `patch`. Standardize features relative to the specific patch cycle, since a champion's strength changes drastically between updates.

---

## 4. Phase 3: Model Selection & Training
* **Model Choices:** 
  * Primary: **XGBoost** or **LightGBM** (highly robust for sparse tabular champion matrices).
  * Secondary: Multi-Layer Perceptron (**MLP Neural Network**) utilizing trainable champion embedding layers.
* **Evaluation Strategy:**
  * **Do not use standard K-Fold cross-validation.** It introduces future-leakage (training on data from June to predict a game in March).
  * **Use Time-Series/Chronological Splitting:** Train the model on older tournament patches (e.g., Patches 14.01 to 14.15) and validate performance strictly on the subsequent patches (e.g., Patches 14.16 and 14.17).
* **Loss Metric:** Optimization target must be `binary_crossentropy` or `logloss`.

---

## 5. Phase 4: Value Betting & Betting Evaluation Engine
Implement an inference script (`src/inference.py`) that acts as a real-time decision tool:
* **Win Probability Output:** Ensure model outputs a calibrated decimal probability (e.g., Blue Win Probability = `0.58`).
* **Value Calculation Formula:** 
  $$\text{Expected Value (EV)} = (\text{Model Probability} \times \text{Decimal Odds}) - 1$$
* **Execution Logic:** Only trigger a trade or bet recommendation if $\text{EV} > 0.03$ (a 3% edge over the bookmaker's listed odds).

---

## 6. Execution Instructions for the Agent
1. Start by drafting a lightweight `src/ingestion.py` mockup using mock data or a small CSV download to verify the pipeline structure.
2. Output a summary report showing feature shapes and class balances before training models.
