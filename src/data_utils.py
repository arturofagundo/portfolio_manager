import glob
import json
import os
import re
from dataclasses import dataclass, field
from typing import cast

import polars as pl

# --- DATA STRUCTURES ---


@dataclass
class FundInfo:
    symbol: str = ""
    asset_class: str = "Other/Unclassified"
    composition: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FundInfo":
        return cls(
            symbol=str(data.get("Symbol", "")),
            asset_class=str(data.get("Asset Class", "Other/Unclassified")),
            composition=cast(dict[str, float], data.get("Composition", {})),
        )

    def to_dict(self) -> dict[str, object]:
        res: dict[str, object] = {
            "Symbol": self.symbol,
            "Asset Class": self.asset_class,
        }
        if self.composition:
            res["Composition"] = self.composition
        return res


# --- FILE UTILS ---


def get_latest_file(directory: str, pattern: str = "*.csv") -> str | None:
    """Find the latest file in a directory based on the YYYY-MM-DD prefix."""
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    files.sort(reverse=True)
    return files[0]


def clean_currency(series: pl.Expr) -> pl.Expr:
    """Clean currency strings and convert to float."""
    return (
        series.cast(pl.String)
        .str.replace_all(r"[\$,\s\(\)]", "")
        .str.replace_all("-", "0")
        .cast(pl.Float64)
    )


# --- MAPPING UTILS ---


def load_fund_info() -> dict[str, FundInfo]:
    """Loads all fund information configurations."""
    path = "data/mappings/fund_information.json"
    os.makedirs("data/mappings", exist_ok=True)

    if not os.path.exists(path):
        return {}

    try:
        with open(path) as f:
            data = cast(dict[str, dict[str, object]], json.load(f))
            return {k: FundInfo.from_dict(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def save_fund_info(fund_map: dict[str, FundInfo]) -> None:
    """Saves fund information configurations to disk."""
    path = "data/mappings/fund_information.json"
    os.makedirs("data/mappings", exist_ok=True)
    with open(path, "w") as f:
        json.dump({k: v.to_dict() for k, v in fund_map.items()}, f, indent=4)


# --- DATA DISCOVERY ---


def get_all_available_funds() -> dict[str, str]:
    """
    Scans data/summaries and data/options to find every unique fund name.
    Returns a dictionary of {fund_name: symbol}.
    """
    funds: dict[str, str] = {}  # fund_name -> symbol

    # Junk patterns to exclude from fund list
    exclude_patterns = [
        r"\$\d+",  # Dollar amounts
        r"FUND I OWN",  # Metadata
        r"Subtotal",  # Totals
        r"Total",  # Totals
        r"per \$1,000",  # Metadata
        r"—\s*\|",  # Separators
        r"\|\s*\d+",  # Ticker/ID lines like "DFFVX | 2977"
        r"Data unavailable",
        r"^\s*$",  # Empty/Whitespace
        r"Sector Funds",
        r"Target Date",
        r"Index Investments",
        r"Active and Specialty",
        r"Objective-Based",
        r"Investments",
        r"Enhanced Core Menu",
        r"Fund Name",
        r"Menu",
        r"Core Menu",
    ]

    def clean_name(name: object) -> str | None:
        if not name:
            return None
        s = str(name).replace("opens in new tab", "").strip()
        s = re.sub(r"(?<=[a-zA-Z])\s*\d{1,2}$", "", s).strip()
        if "|" in s or "Data unavailable" in s or len(s) < 3:
            return None
        if s.lower() in [
            "fund name",
            "enhanced core menu",
            "description",
            "menu",
            "core menu",
        ]:
            return None
        return s

    # Scan all CSVs in both directories
    all_files = glob.glob("data/summaries/**/*.csv", recursive=True) + glob.glob(
        "data/options/**/*.csv", recursive=True
    )

    for f in all_files:
        try:
            df = pl.read_csv(f, truncate_ragged_lines=True)

            # Map column names to potential roles
            name_cols = [c for c in ["Fund name", "Description"] if c in df.columns]
            # Fallback to first column if neither found
            if not name_cols and len(df.columns) > 0:
                name_cols = [df.columns[0]]

            symbol_col = "Symbol" if "Symbol" in df.columns else None

            for col in name_cols:
                if col not in df.columns:
                    continue
                # Get both name and potentially symbol
                if symbol_col:
                    unique_cols = list({col, symbol_col})
                    temp_df = df.select([pl.col(c) for c in unique_cols]).filter(
                        pl.col(col).is_not_null()
                    )
                    for row in temp_df.to_dicts():
                        cleaned = clean_name(row[col])  # type: ignore
                        if cleaned and not any(
                            re.search(p, cleaned) for p in exclude_patterns
                        ):
                            sym = (
                                str(row[symbol_col]).strip() if row[symbol_col] else ""  # type: ignore
                            )
                            # If we already have a symbol, don't overwrite with empty
                            if cleaned not in funds or not funds[cleaned]:
                                funds[cleaned] = sym
                else:
                    vals = (
                        df.select(pl.col(col))
                        .filter(pl.col(col).is_not_null())
                        .to_series()
                        .to_list()
                    )
                    for v in vals:  # type: ignore
                        cleaned = clean_name(str(v) if v is not None else None)  # type: ignore
                        if cleaned and not any(
                            re.search(p, cleaned) for p in exclude_patterns
                        ):
                            if cleaned not in funds:
                                funds[cleaned] = ""
        except (pl.exceptions.ComputeError, OSError):
            pass

    # 3. Include sub-funds from existing compositions
    fund_info = load_fund_info()
    for info in fund_info.values():
        for sf in info.composition.keys():
            cleaned = clean_name(sf)
            if cleaned and cleaned not in funds:
                funds[cleaned] = ""

    return funds
