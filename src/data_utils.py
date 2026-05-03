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


# --- PORTFOLIO LOADING ---


def load_401k_summary(file_path: str | None, account_name: str) -> pl.DataFrame | None:
    if not file_path:
        return None
    df = pl.read_csv(file_path, truncate_ragged_lines=True)
    df = df.filter(
        pl.col("Quantity").cast(pl.String).is_not_null()
        & (pl.col("Quantity").cast(pl.String) != "")
    )
    # Handle different column names for value and investment
    value_col = (
        "Current balance" if "Current balance" in df.columns else "Current Value"
    )
    investment_col = "Fund name" if "Fund name" in df.columns else "Description"
    df = df.with_columns(
        [
            clean_currency(pl.col(value_col)).alias("value"),
            clean_currency(pl.col("Quantity")).alias("quantity"),
            pl.lit("401K").alias("type"),
            pl.lit(account_name).alias("account"),
            pl.col(investment_col).alias("investment"),
        ]
    )
    return df.select(["type", "account", "investment", "value", "quantity"])


def load_ira_summary(file_path: str | None, account_name: str) -> pl.DataFrame | None:
    if not file_path:
        return None
    df = pl.read_csv(file_path, truncate_ragged_lines=True)
    df = df.filter(
        pl.col("Current Value").is_not_null() & (pl.col("Current Value") != "")
    )
    df = df.with_columns(
        [
            clean_currency(pl.col("Current Value")).alias("value"),
            clean_currency(pl.col("Quantity")).alias("quantity"),
            pl.lit("IRA").alias("type"),
            pl.lit(account_name).alias("account"),
            pl.col("Description").alias("investment"),
        ]
    )
    return df.select(["type", "account", "investment", "value", "quantity"])


def get_all_holdings() -> tuple[pl.DataFrame, dict[str, str]]:
    """Loads all holdings from data/summaries/ and returns (combined_df, latest_dates)."""
    summaries_dir = "data/summaries"
    all_holdings: list[pl.DataFrame] = []
    latest_dates: dict[str, str] = {}

    if os.path.exists(summaries_dir):
        for account_dir in os.listdir(summaries_dir):
            full_path = os.path.join(summaries_dir, account_dir)
            if not os.path.isdir(full_path):
                continue

            latest_file = get_latest_file(full_path)
            if not latest_file:
                continue

            # Determine type (401K vs IRA) based on directory name
            is_ira = "IRA" in account_dir.upper()
            acc_type = "IRA" if is_ira else "401K"

            # Extract date for metrics
            date_str = os.path.basename(latest_file).split("_")[0]
            if acc_type not in latest_dates or date_str > latest_dates[acc_type]:
                latest_dates[acc_type] = date_str

            acc_name_clean = account_dir.replace("_", " ")
            if is_ira:
                df = load_ira_summary(latest_file, acc_name_clean)
            else:
                df = load_401k_summary(latest_file, acc_name_clean)

            if df is not None:
                all_holdings.append(df)

    if not all_holdings:
        return pl.DataFrame(), latest_dates

    return pl.concat(all_holdings), latest_dates


def get_all_account_names() -> list[str]:
    """Returns all account names found in data/summaries based on folder names."""
    summaries_dir = "data/summaries"
    if not os.path.exists(summaries_dir):
        return []
    return sorted(
        [
            d.replace("_", " ")
            for d in os.listdir(summaries_dir)
            if os.path.isdir(os.path.join(summaries_dir, d))
        ]
    )


def expand_holdings(df: pl.DataFrame, fund_info: dict[str, FundInfo]) -> pl.DataFrame:
    """
    Recursively expand investments into their underlying asset classes.
    """
    rows: list[dict[str, object]] = []

    def process_investment(
        row_dict: dict[str, object],
        current_investment: str,
        current_value: float,
        is_top_level: bool = True,
    ) -> None:
        # 1. Check if fund has explicit composition
        info = fund_info.get(current_investment)

        if info and info.composition:
            for sub_fund, weight in info.composition.items():
                # When expanding a composite fund, we mark it as such
                process_investment(
                    row_dict, sub_fund, current_value * weight, is_top_level=False
                )
        else:
            # 2. Assign asset class
            ac = "Other/Unclassified"
            if info:
                ac = info.asset_class
            else:
                # Fallback to partial match if not in map exactly
                for name, data in fund_info.items():
                    if name.lower() in current_investment.lower():
                        ac = data.asset_class
                        break

            new_row = row_dict.copy()
            new_row["investment_actual"] = current_investment
            new_row["asset_class"] = ac
            new_row["value"] = current_value
            # Mark as composite if the top-level investment name differs from the leaf investment
            new_row["is_composite"] = row_dict["investment"] != current_investment
            rows.append(new_row)

    for row in df.to_dicts():
        process_investment(row, str(row["investment"]), float(row["value"]))  # type: ignore

    if not rows:
        return pl.DataFrame()

    return pl.from_dicts(rows)


def validate_summary_csv(df: pl.DataFrame, acc_type: str) -> tuple[bool, str]:
    """Validates that a DataFrame has the required columns for its account type."""
    cols = df.columns
    if acc_type == "401K":
        required = ["Fund name", "Quantity", "Current balance"]
    else:  # IRA
        required = ["Description", "Quantity", "Current Value"]

    missing = [c for c in required if c not in cols]
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}"
    return True, ""


# --- ACCOUNT CONSTRAINTS ---


def get_account_summaries() -> pl.DataFrame:
    """Returns a DataFrame with [account, total_value]."""
    raw, _ = get_all_holdings()
    if raw.is_empty():
        return pl.DataFrame()
    return raw.group_by("account").agg(pl.col("value").sum())


def get_account_menus(
    fund_info: dict[str, FundInfo],
) -> dict[str, dict[str, list[str]]]:
    """
    Returns a mapping of account_name -> {asset_class: [fund_names]}.
    """
    menus: dict[str, dict[str, list[str]]] = {}
    options_dir = "data/options"

    options_files = glob.glob(os.path.join(options_dir, "**/*.csv"), recursive=True)

    summaries_dir = "data/summaries"
    accounts = (
        [d.replace("_", " ") for d in os.listdir(summaries_dir)]
        if os.path.exists(summaries_dir)
        else []
    )

    for account in accounts:
        menus[account] = {}
        matched_any = False

        # 1. Try to find a specific options file for this account
        for f in options_files:
            folder_name = os.path.basename(os.path.dirname(f))
            # Match if folder name is in account name (e.g., "Google" in "Google 401K")
            # OR if account name is in folder name (e.g., "Arturo ROTH IRA" matches folder "Arturo_ROTH_IRA")
            folder_clean = folder_name.lower().replace("_", " ")
            acc_clean = account.lower().replace("_", " ")

            if folder_clean in acc_clean or acc_clean in folder_clean:
                matched_any = True
                try:
                    df = pl.read_csv(f, truncate_ragged_lines=True)
                    name_col = (
                        "Fund name" if "Fund name" in df.columns else df.columns[0]
                    )
                    for fund_name in cast(list[object], df[name_col].to_list()):
                        fn: str = str(fund_name)
                        info = fund_info.get(fn)

                        # Fallback: try case-insensitive or substring match if exact fails
                        if not info:
                            for k, v in fund_info.items():
                                if fn.lower() in k.lower() or k.lower() in fn.lower():
                                    info = v
                                    break

                        if info:
                            # Handle composite funds vs single asset funds
                            classes: list[str] = []
                            if info.composition:
                                for sub_fund in info.composition.keys():
                                    sub_info = fund_info.get(sub_fund)
                                    if sub_info:
                                        classes.append(sub_info.asset_class)
                            else:
                                classes.append(info.asset_class)

                            for ac in set(classes):
                                if ac not in menus[account]:
                                    menus[account][ac] = []
                                if fn not in menus[account][ac]:
                                    menus[account][ac].append(fn)
                except (pl.exceptions.ComputeError, OSError):
                    pass

        # 2. If no specific menu found and it's an IRA, default to Arturo's menu
        if not matched_any and "IRA" in account.upper():
            # Find the Arturo_ROTH_IRA menu if it exists
            arturo_acc = next((a for a in menus.keys() if "ARTURO" in a.upper()), None)
            if arturo_acc and menus[arturo_acc]:
                menus[account] = menus[arturo_acc]
            else:
                # If Arturo's menu hasn't been loaded yet, try to load it specifically
                for f in options_files:
                    if "Arturo_ROTH_IRA" in f:
                        try:
                            df = pl.read_csv(f, truncate_ragged_lines=True)
                            name_col = (
                                "Fund name"
                                if "Fund name" in df.columns
                                else df.columns[0]
                            )
                            for fund_name in cast(list[object], df[name_col].to_list()):
                                fn = str(fund_name)
                                info = fund_info.get(fn)
                                if info:
                                    classes = (
                                        [
                                            sub_info.asset_class
                                            for sf in info.composition.keys()
                                            if (sub_info := fund_info.get(sf))
                                        ]
                                        if info.composition
                                        else [info.asset_class]
                                    )
                                    for ac in set(classes):
                                        if ac not in menus[account]:
                                            menus[account][ac] = []
                                        if fn not in menus[account][ac]:
                                            menus[account][ac].append(fn)
                        except (pl.exceptions.ComputeError, OSError):
                            pass

    return menus


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
