"""
Champion Matcher and OCR Post-Processor for LoL Esports Vision Pipeline.
Provides fuzzy lexicon matching, shorthand resolution, and role alignment.
"""
import os
import re
import json
import difflib
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("ChampionMatcher")

CHAMPION_ALIASES = {
    "j4": "Jarvan IV",
    "jarvan": "Jarvan IV",
    "jarvan4": "Jarvan IV",
    "jarvaniv": "Jarvan IV",
    "tf": "Twisted Fate",
    "twistedfate": "Twisted Fate",
    "mf": "Miss Fortune",
    "missfortune": "Miss Fortune",
    "tk": "Tahm Kench",
    "tahm": "Tahm Kench",
    "tahmkench": "Tahm Kench",
    "gp": "Gangplank",
    "gangplank": "Gangplank",
    "asol": "Aurelion Sol",
    "aurelionsol": "Aurelion Sol",
    "aurelion": "Aurelion Sol",
    "ksante": "K'Sante",
    "k'sante": "K'Sante",
    "ksant": "K'Sante",
    "k sante": "K'Sante",
    "renata": "Renata Glasc",
    "renataglasc": "Renata Glasc",
    "glasc": "Renata Glasc",
    "wukong": "Wukong",
    "monkeyking": "Wukong",
    "nunu": "Nunu & Willump",
    "nunu&willump": "Nunu & Willump",
    "nunuwillump": "Nunu & Willump",
    "willump": "Nunu & Willump",
    "drmundo": "Dr. Mundo",
    "dr.mundo": "Dr. Mundo",
    "mundo": "Dr. Mundo",
    "kaisa": "Kai'Sa",
    "kai'sa": "Kai'Sa",
    "chogath": "Cho'Gath",
    "cho'gath": "Cho'Gath",
    "khazix": "Kha'Zix",
    "kha'zix": "Kha'Zix",
    "velkoz": "Vel'Koz",
    "vel'koz": "Vel'Koz",
    "kogmaw": "Kog'Maw",
    "kog'maw": "Kog'Maw",
    "belveth": "Bel'Veth",
    "bel'veth": "Bel'Veth",
    "reksai": "Rek'Sai",
    "rek'sai": "Rek'Sai",
    "xinzhao": "Xin Zhao",
    "xin": "Xin Zhao",
    "leesin": "Lee Sin",
    "lee": "Lee Sin",
    "masteryi": "Master Yi",
    "yi": "Master Yi",
    "leblanc": "LeBlanc",
    "cait": "Caitlyn",
    "cass": "Cassiopeia",
    "heimer": "Heimerdinger",
    "mali": "Malzahar",
    "malz": "Malzahar",
    "vlad": "Vladimir",
    "ww": "Warwick",
    "noc": "Nocturne",
    "blitz": "Blitzcrank",
    "morg": "Morgana",
    "morganna": "Morgana",
    "caitlyn": "Caitlyn",
    "trist": "Tristana",
    "seju": "Sejuani",
    "sej": "Sejuani",
    "volibear": "Volibear",
    "voli": "Volibear",
    "naut": "Nautilus",
    "nautilus": "Nautilus",
    "alistar": "Alistar",
    "ali": "Alistar",
    "ez": "Ezreal",
    "ezreal": "Ezreal",
    "luc": "Lucian",
    "lucian": "Lucian",
    "orianna": "Orianna",
    "ori": "Orianna",
    "syndra": "Syndra",
    "azir": "Azir",
    "ahri": "Ahri",
    "yone": "Yone",
    "yasuo": "Yasuo",
    "viego": "Viego",
    "rumble": "Rumble",
    "gnar": "Gnar",
    "jax": "Jax",
    "camille": "Camille",
    "renekton": "Renekton",
    "renek": "Renekton",
    "smolder": "Smolder",
    "ziggs": "Ziggs",
    "zeri": "Zeri",
    "ashe": "Ashe",
    "varus": "Varus",
    "jhin": "Jhin",
    "kallista": "Kalista",
    "kalista": "Kalista",
    "leona": "Leona",
    "rell": "Rell",
    "braum": "Braum",
    "lulu": "Lulu",
    "nami": "Nami",
    "rakan": "Rakan",
    "poppy": "Poppy",
    "maokai": "Maokai",
    "ivern": "Ivern",
    "nidalee": "Nidalee",
    "nida": "Nidalee",
    "kindred": "Kindred",
    "karthus": "Karthus",
    "taliyah": "Taliyah",
    "sylas": "Sylas",
    "akali": "Akali",
    "corki": "Corki",
    "jayce": "Jayce",
    "tristana": "Tristana",
    "galio": "Galio",
    "kennen": "Kennen",
    "sion": "Sion",
    "ornn": "Ornn",
    "gragas": "Gragas",
    "urgot": "Urgot",
    "fiora": "Fiora",
    "aatrox": "Aatrox",
    "ambessa": "Ambessa",
    "mel": "Mel",
    "aurora": "Aurora",
    "hwei": "Hwei",
    "briar": "Briar",
    "naafiri": "Naafiri",
    "milio": "Milio"
}

TEAM_SYNONYMS = {
    "T1": "T1", "SKT": "T1", "SKT T1": "T1", "SK TELECOM T1": "T1",
    "GEN": "Gen.G", "GEN.G": "Gen.G", "GENG": "Gen.G", "GEN.G ESPORTS": "Gen.G",
    "HLE": "Hanwha Life Esports", "HANWHA": "Hanwha Life Esports", "HANWHA LIFE": "Hanwha Life Esports",
    "DK": "Dplus KIA", "DPLUS": "Dplus KIA", "DWG": "Dplus KIA", "DAMWON": "Dplus KIA", "DAMWON GAMING": "Dplus KIA",
    "KT": "KT Rolster", "KT ROLSTER": "KT Rolster",
    "BFX": "BNK FEARX", "FEARX": "BNK FEARX", "FOX": "BNK FEARX", "SB": "BNK FEARX",
    "KDF": "Kwangdong Freecs", "FREECS": "Kwangdong Freecs",
    "NS": "Nongshim RedForce", "NONGSHIM": "Nongshim RedForce",
    "DRX": "DRX", "DRAGONX": "DRX",
    "BRO": "OKSavingsBank BRION", "BRION": "OKSavingsBank BRION",
    "BLG": "Bilibili Gaming", "BILIBILI": "Bilibili Gaming", "BILIBILI GAMING": "Bilibili Gaming",
    "TES": "Top Esports", "TOP": "Top Esports", "TOP ESPORTS": "Top Esports",
    "JDG": "JD Gaming", "JD": "JD Gaming", "JD GAMING": "JD Gaming",
    "LNG": "LNG Esports", "LNG ESPORTS": "LNG Esports",
    "WBG": "Weibo Gaming", "WEIBO": "Weibo Gaming", "WEIBO GAMING": "Weibo Gaming",
    "FPX": "FunPlus Phoenix", "FUNPLUS": "FunPlus Phoenix",
    "NIP": "Ninjas in Pyjamas", "NINJAS": "Ninjas in Pyjamas",
    "AL": "Anyone's Legend",
    "IG": "Invictus Gaming", "INVICTUS": "Invictus Gaming",
    "EDG": "Edward Gaming", "EDWARD": "Edward Gaming",
    "RNG": "Royal Never Give Up", "ROYAL": "Royal Never Give Up",
    "OMG": "OMG",
    "TT": "ThunderTalk Gaming", "THUNDERTALK": "ThunderTalk Gaming",
    "LGD": "LGD Gaming", "LGD GAMING": "LGD Gaming",
    "WE": "Team WE", "TEAM WE": "Team WE",
    "UP": "Ultra Prime", "ULTRA PRIME": "Ultra Prime",
    "RA": "Rare Atom", "RARE ATOM": "Rare Atom",
    "G2": "G2 Esports", "G2 ESPORTS": "G2 Esports",
    "FNC": "Fnatic", "FNATIC": "Fnatic",
    "BDS": "Team BDS", "TEAM BDS": "Team BDS",
    "MDK": "MAD Lions KOI", "MAD": "MAD Lions KOI", "MAD LIONS": "MAD Lions KOI", "MKOI": "MAD Lions KOI",
    "KOI": "MAD Lions KOI",
    "SK": "SK Gaming", "SK GAMING": "SK Gaming",
    "TH": "Team Heretics", "HERETICS": "Team Heretics", "HER": "Team Heretics",
    "VIT": "Team Vitality", "VITALITY": "Team Vitality",
    "KC": "Karmine Corp", "KARMINE": "Karmine Corp",
    "GX": "GIANTX", "GIANTS": "GIANTX",
    "RGE": "Rogue", "ROGUE": "Rogue",
    "NAVI": "Natus Vincere",
    "SHFT": "Team Shift",
    "FLY": "FlyQuest", "FLYQUEST": "FlyQuest",
    "TL": "Team Liquid", "LIQUID": "Team Liquid", "TEAM LIQUID": "Team Liquid", "TLAW": "Team Liquid",
    "C9": "Cloud9", "CLOUD9": "Cloud9",
    "100": "100 Thieves", "100 THIEVES": "100 Thieves", "100T": "100 Thieves",
    "DIG": "Dignitas", "DIGNITAS": "Dignitas",
    "SR": "Shopify Rebellion", "SHOPIFY": "Shopify Rebellion",
    "IMT": "Immortals", "IMMORTALS": "Immortals",
    "LYON": "Lyon Gaming"
}

class ChampionMatcher:
    def __init__(self, metadata_path: Optional[str] = None):
        if not metadata_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            metadata_path = os.path.join(base_dir, "config", "champion_metadata.json")
            
        self.metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
                
        self.canonical_champions = list(self.metadata.keys()) if self.metadata else []
        self._lookup_map = self._build_lookup_map()
        logger.info(f"ChampionMatcher initialized with {len(self.canonical_champions)} canonical champions.")

    def _build_lookup_map(self) -> Dict[str, str]:
        lookup = {}
        for champ in self.canonical_champions:
            cleaned = self._clean_str(champ)
            lookup[cleaned] = champ
            lookup[champ.lower()] = champ
            
        for alias, canonical in CHAMPION_ALIASES.items():
            lookup[self._clean_str(alias)] = canonical
            lookup[alias.lower()] = canonical
            
        return lookup

    @staticmethod
    def _clean_str(s: str) -> str:
        if not s:
            return ""
        # Remove apostrophes, spaces, periods, dashes, and convert to lowercase
        return re.sub(r"[^a-zA-Z0-9]", "", s).lower()

    def match_champion(self, raw_text: str, cutoff: float = 0.68) -> Tuple[Optional[str], float]:
        """
        Matches raw OCR text against champion lexicon.
        Returns (canonical_name, confidence_score).
        """
        if not raw_text or not isinstance(raw_text, str):
            return None, 0.0
            
        cleaned = self._clean_str(raw_text)
        if not cleaned or len(cleaned) < 2:
            return None, 0.0
            
        # 1. Exact clean match
        if cleaned in self._lookup_map:
            return self._lookup_map[cleaned], 1.0
            
        # 2. Substring match for compound names (only if high ratio overlap)
        for key, canonical in self._lookup_map.items():
            if len(key) >= 4:
                if cleaned == key:
                    return canonical, 1.0
                elif len(cleaned) >= 4 and cleaned in key:
                    if len(cleaned) / len(key) >= 0.75:
                        return canonical, 0.85

        # 3. Fuzzy Levenshtein match across canonical names
        candidates = list(self._lookup_map.keys())
        matches = difflib.get_close_matches(cleaned, candidates, n=1, cutoff=cutoff)
        if matches:
            matched_key = matches[0]
            # Verify length is comparable to avoid matching "BLVESIDET1" to "Bel'Veth"
            if abs(len(cleaned) - len(matched_key)) <= 3:
                canonical = self._lookup_map[matched_key]
                ratio = difflib.SequenceMatcher(None, cleaned, matched_key).ratio()
                return canonical, float(ratio)

        return None, 0.0

    def match_team(self, raw_text: str) -> Optional[str]:
        """
        Normalizes team code or name from OCR text (e.g. 'BLUE SIDE: T1', 'RED: GEN', 'KT', 'FlyQuest').
        """
        if not raw_text:
            return None
            
        # Clean common broadcast overlay noise words
        cleaned_text = re.sub(r"(?i)\b(blue\s*side|red\s*side|blue|red|team|vs|v|game\s*\d+|match\s*\d+)\b", "", raw_text)
        cleaned_text = cleaned_text.replace(":", " ").replace("-", " ").strip()
        
        candidates_to_try = [raw_text.strip(), cleaned_text]
        # Also try individual tokens if longer string
        candidates_to_try.extend(cleaned_text.split())
        candidates_to_try.extend(raw_text.replace(":", " ").replace("-", " ").split())
        
        for cand in candidates_to_try:
            cand_strip = cand.strip()
            if not cand_strip:
                continue
            cand_upper = cand_strip.upper()
            cand_clean = self._clean_str(cand_strip).upper()
            
            # Check direct alias
            if cand_upper in TEAM_SYNONYMS:
                return TEAM_SYNONYMS[cand_upper]
                
            for k, v in TEAM_SYNONYMS.items():
                if cand_clean == self._clean_str(k).upper():
                    return v
                    
            # Close match
            matches = difflib.get_close_matches(cand_upper, list(TEAM_SYNONYMS.keys()), n=1, cutoff=0.75)
            if matches:
                return TEAM_SYNONYMS[matches[0]]
                
        return cleaned_text if cleaned_text else raw_text.strip()
