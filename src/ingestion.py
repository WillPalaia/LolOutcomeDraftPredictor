"""
Data Ingestion and Preprocessing Module.
Handles downloading, cleaning, and formatting Oracle's Elixir competitive match datasets.
"""
import os
import re
import io
import requests
import pandas as pd
import numpy as np
import yaml
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def download_gdrive_file(file_id: str, destination: str) -> bool:
    """Download large file from Google Drive with cookie/warning handling."""
    if os.path.exists(destination) and os.path.getsize(destination) > 1000000:
        logger.info(f"File already exists at {destination} ({os.path.getsize(destination)/(1024*1024):.2f} MB), skipping download.")
        return True

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    url = "https://drive.google.com/uc?export=download"
    params = {'id': file_id}
    logger.info(f"Connecting to Google Drive for file ID: {file_id}...")
    
    response = session.get(url, params=params, stream=True, timeout=20)
    content_disposition = response.headers.get('content-disposition', '')
    
    if 'attachment' not in content_disposition:
        text = response.content.decode('utf-8', errors='ignore')
        match = re.search(r'href="(\/uc\?export=download[^"]+)"', text)
        if match:
            confirm_url = "https://drive.google.com" + match.group(1).replace("&amp;", "&")
            response = session.get(confirm_url, stream=True, timeout=30)
        else:
            match_uuid = re.search(r'action="(https:\/\/[^"]+)"', text)
            if match_uuid:
                action_url = match_uuid.group(1)
                inputs = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', text))
                response = session.post(action_url, data=inputs, stream=True, timeout=30)

    total_bytes = 0
    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                total_bytes += len(chunk)
    
    logger.info(f"Saved {destination} ({total_bytes / (1024*1024):.2f} MB)")
    return os.path.exists(destination) and os.path.getsize(destination) > 1000

def load_and_standardize_year_csv(file_path: str) -> pd.DataFrame:
    """
    Parse Oracle's Elixir raw CSV (which has 12 rows per match) into 1 standardized row per match.
    """
    logger.info(f"Parsing match records from {file_path}...")
    df = pd.read_csv(file_path, low_memory=False)
    
    # Filter valid games
    if 'datacompleteness' in df.columns:
        df = df[df['datacompleteness'] != 'partial'].copy()
    
    # Ensure required columns exist
    required_cols = ['gameid', 'date', 'league', 'split', 'patch', 'side', 'position', 'teamname', 'result']
    for col in required_cols:
        if col not in df.columns:
            logger.warning(f"Missing column {col} in {file_path}")
            return pd.DataFrame()
            
    # Clean patch version (e.g. 14.1, 14.10)
    df['patch'] = df['patch'].astype(str).str.strip()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date', 'gameid', 'side', 'result']).sort_values('date')

    # Separate team summary rows and player rows
    team_mask = df['position'].str.lower() == 'team'
    player_mask = ~team_mask
    
    df_teams = df[team_mask].copy()
    df_players = df[player_mask].copy()
    
    # Pivot player picks by position
    # Standard positions: top, jng, mid, bot, sup
    df_players['position'] = df_players['position'].str.lower().str.strip()
    
    # Pivot picks
    picks_pivoted = df_players.pivot_table(
        index=['gameid', 'side'],
        columns='position',
        values=['champion', 'playername'],
        aggfunc='first'
    )
    
    # Flatten multiindex columns
    picks_pivoted.columns = [f"{col[1]}_{col[0]}" for col in picks_pivoted.columns]
    picks_pivoted = picks_pivoted.reset_index()

    # Merge team info with picks
    merged_teams = pd.merge(
        df_teams,
        picks_pivoted,
        on=['gameid', 'side'],
        how='inner'
    )

    # Pivot Blue and Red side into single row per game
    blue_games = merged_teams[merged_teams['side'].str.lower() == 'blue'].copy()
    red_games = merged_teams[merged_teams['side'].str.lower() == 'red'].copy()
    
    # Rename columns with prefix
    blue_cols_rename = {
        'teamname': 'blue_team',
        'result': 'blue_win',
        'ban1': 'blue_ban1', 'ban2': 'blue_ban2', 'ban3': 'blue_ban3', 'ban4': 'blue_ban4', 'ban5': 'blue_ban5',
        'top_champion': 'blue_top', 'jng_champion': 'blue_jng', 'mid_champion': 'blue_mid', 'bot_champion': 'blue_bot', 'sup_champion': 'blue_sup',
        'top_playername': 'blue_player_top', 'jng_playername': 'blue_player_jng', 'mid_playername': 'blue_player_mid', 'bot_playername': 'blue_player_bot', 'sup_playername': 'blue_player_sup'
    }
    
    red_cols_rename = {
        'teamname': 'red_team',
        'ban1': 'red_ban1', 'ban2': 'red_ban2', 'ban3': 'red_ban3', 'ban4': 'red_ban4', 'ban5': 'red_ban5',
        'top_champion': 'red_top', 'jng_champion': 'red_jng', 'mid_champion': 'red_mid', 'bot_champion': 'red_bot', 'sup_champion': 'red_sup',
        'top_playername': 'red_player_top', 'jng_playername': 'red_player_jng', 'mid_playername': 'red_player_mid', 'bot_playername': 'red_player_bot', 'sup_playername': 'red_player_sup'
    }

    base_cols = ['gameid', 'date', 'league', 'split', 'playoffs', 'patch', 'gamelength']
    available_base = [c for c in base_cols if c in blue_games.columns]
    
    blue_subset = blue_games[available_base + [c for c in blue_cols_rename.keys() if c in blue_games.columns]].rename(columns=blue_cols_rename)
    red_subset = red_games[['gameid'] + [c for c in red_cols_rename.keys() if c in red_games.columns]].rename(columns=red_cols_rename)
    
    final_games = pd.merge(blue_subset, red_subset, on='gameid', how='inner')
    
    # Filter rows with complete picks for all 10 roles
    roles = ['blue_top', 'blue_jng', 'blue_mid', 'blue_bot', 'blue_sup', 'red_top', 'red_jng', 'red_mid', 'red_bot', 'red_sup']
    valid_picks = final_games.dropna(subset=roles).copy()
    
    logger.info(f"Extracted {len(valid_picks)} complete matches from {file_path}")
    return valid_picks

def ingest_dataset(config_path: str = "config/default_config.yaml") -> pd.DataFrame:
    """Main ingestion pipeline to download and harmonize all yearly datasets."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    raw_dir = config['data']['raw_dir']
    processed_dir = config['data']['processed_dir']
    gdrive_ids = config['data']['gdrive_file_ids']
    years = config['data']['years']
    
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    
    all_dfs = []
    for year in years:
        file_id = gdrive_ids.get(year)
        dest_file = os.path.join(raw_dir, f"{year}_LoL_esports_match_data_from_OraclesElixir.csv")
        
        if file_id:
            download_gdrive_file(file_id, dest_file)
            
        if os.path.exists(dest_file):
            df_year = load_and_standardize_year_csv(dest_file)
            if not df_year.empty:
                df_year['year'] = year
                all_dfs.append(df_year)
                
    if not all_dfs:
        raise RuntimeError("No match data could be loaded. Check raw directory or network connectivity.")
        
    combined_df = pd.concat(all_dfs, ignore_index=True)
    combined_df = combined_df.sort_values('date').reset_index(drop=True)
    
    # Save processed outputs
    out_parquet = os.path.join(processed_dir, "matches_standardized.parquet")
    out_csv = os.path.join(processed_dir, "matches_standardized.csv")
    
    try:
        combined_df.to_parquet(out_parquet, index=False)
        logger.info(f"Saved standardized dataset to {out_parquet} ({len(combined_df)} matches)")
    except Exception:
        pass
        
    combined_df.to_csv(out_csv, index=False)
    logger.info(f"Saved standardized dataset to {out_csv} ({len(combined_df)} matches)")
    return combined_df

if __name__ == "__main__":
    ingest_dataset()
