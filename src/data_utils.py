import polars as pl
import os
import glob
import json
import re

# --- FILE UTILS ---

def get_latest_file(directory, pattern="*.csv"):
    """Find the latest file in a directory based on the YYYY-MM-DD prefix."""
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    files.sort(reverse=True)
    return files[0]

def clean_currency(series):
    """Clean currency strings and convert to float."""
    return (
        series.cast(pl.String)
        .str.replace_all(r"[\$,\s\(\)]", "")
        .str.replace_all("-", "0")
        .cast(pl.Float64)
    )

# --- MAPPING UTILS ---

def load_mappings():
    asset_path = "data/mappings/asset_classes.json"
    comp_path = "data/mappings/fund_compositions.json"
    
    os.makedirs("data/mappings", exist_ok=True)
    
    if not os.path.exists(asset_path):
        with open(asset_path, 'w') as f: json.dump({}, f)
    if not os.path.exists(comp_path):
        with open(comp_path, 'w') as f: json.dump({}, f)
        
    try:
        with open(asset_path, 'r') as f: asset_map = json.load(f)
        with open(comp_path, 'r') as f: comp_map = json.load(f)
        return asset_map, comp_map
    except:
        return {}, {}

def save_mappings(asset_map, comp_map):
    os.makedirs("data/mappings", exist_ok=True)
    with open("data/mappings/asset_classes.json", 'w') as f: json.dump(asset_map, f, indent=4)
    with open("data/mappings/fund_compositions.json", 'w') as f: json.dump(comp_map, f, indent=4)

# --- DATA DISCOVERY ---

def get_all_available_funds():
    """
    Scans data/summaries and data/options to find every unique fund name.
    """
    funds = set()
    
    # Junk patterns to exclude from fund list
    exclude_patterns = [
        r"\$\d+",          # Dollar amounts
        r"FUND I OWN",     # Metadata
        r"Subtotal",       # Totals
        r"Total",          # Totals
        r"per \$1,000",    # Metadata
        r"—\s*\|",         # Separators
        r"\|\s*\d+",       # Ticker/ID lines like "DFFVX | 2977"
        r"Data unavailable",
        r"^\s*$",          # Empty/Whitespace
        r"Sector Funds",
        r"Target Date",
        r"Index Investments",
        r"Active and Specialty",
        r"Objective-Based",
        r"Investments",
        r"Enhanced Core Menu",
        r"Fund Name",
        r"Menu",
        r"Core Menu"
    ]
    
    def clean_name(name):
        if not name: return None
        s = str(name).replace("opens in new tab", "").strip()
        
        # Remove trailing footnote digits (e.g., "Fund 15" -> "Fund")
        s = re.sub(r"(?<=[a-zA-Z])\s*\d{1,2}$", "", s).strip()
        
        # Filter out ticker lines or metadata lines explicitly
        if "|" in s or "Data unavailable" in s or len(s) < 5:
            return None
            
        if s.lower() in ["fund name", "enhanced core menu", "description", "menu", "core menu"]:
            return None
            
        return s

    # Scan all CSVs in both directories
    all_files = glob.glob("data/summaries/**/*.csv", recursive=True) + \
                glob.glob("data/options/**/*.csv", recursive=True)
                
    for f in all_files:
        try:
            # We use low_memory=False or similar if needed, but Polars defaults are fine.
            # We check the first two columns of every file as bespoke formats vary.
            df = pl.read_csv(f, truncate_ragged_lines=True)
            
            # Identify columns to check: First two columns are most likely
            cols_to_check = df.columns[:2]
            # Also specifically check 'Description' if it exists (for IRA files)
            if "Description" in df.columns and "Description" not in cols_to_check:
                cols_to_check = list(cols_to_check) + ["Description"]
                
            for col in cols_to_check:
                vals = df.select(pl.col(col)).filter(pl.col(col).is_not_null()).to_series().to_list()
                for v in vals:
                    cleaned = clean_name(v)
                    if cleaned and not any(re.search(p, cleaned) for p in exclude_patterns):
                        # Ensure it doesn't look like a single-word generic header (unless it's a known fund)
                        if len(cleaned.split()) >= 2 or cleaned in ["WASATCH MICROCAP"]:
                            funds.update([cleaned])
        except: pass

    # 3. Include sub-funds from existing compositions
    _, comp_map = load_mappings()
    for sub_funds in comp_map.values():
        for sf in sub_funds.keys():
            cleaned = clean_name(sf)
            if cleaned:
                funds.update([cleaned])
            
    return sorted(list(funds))
