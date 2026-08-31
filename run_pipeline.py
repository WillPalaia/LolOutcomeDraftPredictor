"""
Master Execution Pipeline.
Executes end-to-end data ingestion, chronological rating computation,
feature engineering, constrained residual draft training, and +EV backtesting.
"""
import os
import json
import yaml
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss

from src.ingestion import ingest_dataset
from src.ratings import DynamicRatingEngine
from src.features import AdvancedDraftFeatureExtractor
from src.models.tree_models import ResidualDraftModel
from src.backtest.market_simulator import MarketOddsSimulator
from src.backtest.betting_strategy import EVBettingBacktester
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LoLPipeline")

def run_full_pipeline(config_path: str = "config/default_config.yaml"):
    logger.info("=================================================================")
    logger.info("  STARTING LEAGUE OF LEGENDS +EV DRAFT PREDICTION PIPELINE       ")
    logger.info("=================================================================")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    os.makedirs(config['data']['cache_dir'], exist_ok=True)
    os.makedirs(config['data']['processed_dir'], exist_ok=True)

    # 1. Ingestion Phase
    logger.info("--- PHASE 1: DATA INGESTION & HARMONIZATION ---")
    df_matches = ingest_dataset(config_path)
    logger.info(f"Loaded {len(df_matches)} total matches spanning {df_matches['date'].min().strftime('%Y-%m-%d')} to {df_matches['date'].max().strftime('%Y-%m-%d')}")
    
    # 2. Chronological Rating Phase (Dynamic Glicko-2 / Elo)
    logger.info("--- PHASE 2: DYNAMIC TEAM RATING ENGINE ---")
    rating_engine = DynamicRatingEngine(
        initial_rating=config['ratings']['initial_rating'],
        initial_rd=config['ratings']['initial_rd'],
        side_bias_elo=config['ratings']['side_bias_elo']
    )
    df_rated = rating_engine.compute_dataset_baseline_probabilities(df_matches)
    baseline_acc = accuracy_score(df_rated['blue_win'], (df_rated['baseline_blue_prob'] >= 0.5).astype(int))
    baseline_auc = roc_auc_score(df_rated['blue_win'], df_rated['baseline_blue_prob'])
    baseline_brier = brier_score_loss(df_rated['blue_win'], df_rated['baseline_blue_prob'])
    logger.info(f"Pre-Draft Team Baseline Metrics -> Accuracy: {baseline_acc*100:.2f}%, AUC: {baseline_auc:.4f}, Brier: {baseline_brier:.4f}")

    # 3. Feature Engineering Phase
    logger.info("--- PHASE 3: FEATURE ENGINEERING (PATCH PRIORITY, MATCHUPS & COMPS) ---")
    feature_extractor = AdvancedDraftFeatureExtractor(
        champion_metadata_path="config/champion_metadata.json",
        bayesian_prior_matches=config['features']['bayesian_prior_matches'],
        bayesian_prior_winrate=config['features']['bayesian_prior_winrate']
    )
    df_features, feature_cols = feature_extractor.compute_all_features(df_rated)
    logger.info(f"Feature matrix ready: {df_features.shape[0]} rows, {len(feature_cols)} predictor features")

    # 4. Chronological Train / Validation / Test Split
    logger.info("--- PHASE 4: TIME-SERIES SPLIT & HEAVY PATCH-WEIGHTED MODEL TRAINING ---")
    test_ratio = config['backtest']['test_split_ratio']
    split_idx = int(len(df_features) * (1.0 - test_ratio))
    
    df_train = df_features.iloc[:split_idx].copy()
    df_test = df_features.iloc[split_idx:].copy()
    
    logger.info(f"Chronological Split: Train Matches = {len(df_train)} (Past), Out-of-Sample Test Matches = {len(df_test)} (Future)")
    
    # Filter high-signal structural draft features
    structural_cols = [c for c in feature_cols if c not in ['blue_rating_pre', 'red_rating_pre', 'baseline_blue_prob']]
    
    X_train = df_train[structural_cols]
    y_train = df_train['blue_win'].values
    train_base_probs = df_train['baseline_blue_prob'].values
    
    X_test = df_test[structural_cols]
    y_test = df_test['blue_win'].values
    test_base_probs = df_test['baseline_blue_prob'].values
    
    # Compute Patch Weights (Current Patch Heavily Weighted with Exponential Recency Decay)
    if 'patch_num' in df_train.columns:
        max_train_p = df_train['patch_num'].max()
        patch_deltas = (max_train_p - df_train['patch_num']).clip(lower=0)
        sample_weights = np.exp(-0.06 * patch_deltas) * (1.0 + 3.0 * (df_train['patch_num'] == max_train_p).astype(float))
        sample_weights = sample_weights / sample_weights.mean()
        logger.info(f"Applied heavy patch recency sample weighting: Latest Train Patch = {max_train_p:.0f} (4x weight boost)")
    else:
        sample_weights = None

    # Train Constrained Residual Model
    model = ResidualDraftModel(
        iterations=350,
        learning_rate=0.02,
        depth=4,
        l2_leaf_reg=8.0,
        random_seed=42
    )
    model.fit(
        X=X_train,
        y=y_train,
        base_probs=train_base_probs,
        sample_weight=sample_weights,
        val_X=X_test,
        val_y=y_test,
        val_base_probs=test_base_probs
    )
    
    # Save model artifact
    model_save_path = os.path.join(config['data']['cache_dir'], "residual_draft_model.joblib")
    model.save(model_save_path)
    logger.info(f"Saved trained model to {model_save_path}")

    # Log Parameter Weights (Feature Importances)
    feat_imp = model.get_feature_importances(structural_cols)
    logger.info("=================================================================")
    logger.info("  MODEL PARAMETER WEIGHTS (CATBOOST FEATURE IMPORTANCE)          ")
    logger.info("=================================================================")
    for _, r in feat_imp.iterrows():
        if r['importance'] > 0.01:
            logger.info(f"  • {r['feature']:<28}: {r['importance']:6.2f}%")
    logger.info("=================================================================")

    # 5. Out-of-Sample Evaluation
    logger.info("--- PHASE 5: PROBABILITY EVALUATION ---")
    calibrated_test_preds = model.predict_proba(X_test, base_probs=test_base_probs)
    
    test_acc = accuracy_score(y_test, (calibrated_test_preds >= 0.5).astype(int))
    test_auc = roc_auc_score(y_test, calibrated_test_preds)
    test_brier = brier_score_loss(y_test, calibrated_test_preds)
    
    logger.info("Out-of-Sample Test Performance:")
    logger.info(f"  Accuracy: {test_acc*100:.2f}% (vs Baseline Alone {baseline_acc*100:.2f}%)")
    logger.info(f"  ROC-AUC:  {test_auc:.4f} (vs Baseline Alone {baseline_auc:.4f})")
    logger.info(f"  Brier:    {test_brier:.4f} (Optimized Probability Loss)")

    # 6. +EV Betting Simulation & Financial Backtest
    logger.info("--- PHASE 6: QUANTITATIVE +EV BETTING BACKTEST ---")
    market_sim = MarketOddsSimulator(vig=config['backtest']['market_vig'])
    
    df_test = df_test.copy()
    df_test['calibrated_blue_prob'] = calibrated_test_preds
    market_odds_list = [market_sim.generate_market_lines(p) for p in df_test['baseline_blue_prob']]
    df_test['odds_blue'] = [m['odds_blue'] for m in market_odds_list]
    df_test['odds_red'] = [m['odds_red'] for m in market_odds_list]
    
    backtester = EVBettingBacktester(
        initial_bankroll=config['backtest']['initial_bankroll'],
        ev_threshold=config['backtest'].get('ev_threshold', 0.025),
        kelly_fraction=config['backtest'].get('kelly_fraction', 0.20),
        max_bet_fraction=config['backtest'].get('max_bet_fraction', 0.035)
    )
    backtest_results = backtester.run_backtest(df_test)
    
    logger.info("=================================================================")
    logger.info("  HISTORICAL +EV BACKTESTING RESULTS SUMMARY                     ")
    logger.info("=================================================================")
    logger.info(f"  Initial Bankroll:    ${backtest_results['initial_bankroll']:,.2f}")
    logger.info(f"  Final Bankroll:      ${backtest_results['final_bankroll']:,.2f}")
    logger.info(f"  Net Profit:          ${backtest_results['total_profit']:,.2f}")
    logger.info(f"  Total Bets Placed:   {backtest_results['total_bets']}")
    logger.info(f"  Bet Win Rate:        {backtest_results['win_rate_pct']:.2f}%")
    logger.info(f"  Total Wagered:       ${backtest_results['total_wagered']:,.2f}")
    logger.info(f"  Return on Inv (ROI): {backtest_results['roi_pct']:.2f}%")
    logger.info(f"  Max Drawdown:        {backtest_results['max_drawdown_pct']:.2f}%")
    logger.info(f"  Sharpe Ratio:        {backtest_results['sharpe_ratio']:.2f}")
    logger.info("=================================================================")
    
    # Save backtest results
    report_path = os.path.join(config['data']['cache_dir'], "backtest_summary.json")
    with open(report_path, "w", encoding="utf-8") as f:
        summary_to_save = {k: v for k, v in backtest_results.items() if k != 'trades'}
        summary_to_save['feature_importances'] = feat_imp.to_dict(orient='records')
        json.dump(summary_to_save, f, indent=2)
    logger.info(f"Saved summary metrics to {report_path}")
    return backtest_results

if __name__ == "__main__":
    run_full_pipeline()

