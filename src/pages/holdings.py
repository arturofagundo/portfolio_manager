import os

import altair as alt
import polars as pl
import streamlit as st

from data_utils import FundInfo, clean_currency, get_latest_file, load_fund_info


# --- LOADING LOGIC ---
def load_401k_summary(file_path: str | None, account_name: str) -> pl.DataFrame | None:
    if not file_path:
        return None
    df = pl.read_csv(file_path, truncate_ragged_lines=True)
    df = df.filter(pl.col("Quantity").is_not_null() & (pl.col("Quantity") != ""))
    df = df.with_columns(
        [
            clean_currency(pl.col("Current balance")).alias("value"),
            clean_currency(pl.col("Quantity")).alias("quantity"),
            pl.lit("401K").alias("type"),
            pl.lit(account_name).alias("account"),
            pl.col("Fund name").alias("investment"),
        ]
    )
    return df.select(["type", "account", "investment", "value", "quantity"])


def load_ira_summary(file_path: str | None) -> pl.DataFrame | None:
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
            pl.col("Account Name").alias("account"),
            pl.col("Description").alias("investment"),
        ]
    )
    return df.select(["type", "account", "investment", "value", "quantity"])


# --- ALLOCATION LOGIC ---


def expand_holdings(df: pl.DataFrame, fund_info: dict[str, FundInfo]) -> pl.DataFrame:
    """
    Recursively expand investments into their underlying asset classes.
    """
    rows: list[dict[str, object]] = []

    def process_investment(
        row_dict: dict[str, object], current_investment: str, current_value: float
    ) -> None:
        # 1. Check if fund has explicit composition
        info = fund_info.get(current_investment)

        if info and info.composition:
            for sub_fund, weight in info.composition.items():
                process_investment(row_dict, sub_fund, current_value * weight)
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
            rows.append(new_row)

    for row in df.to_dicts():
        process_investment(row, str(row["investment"]), float(row["value"]))  # type: ignore

    return pl.from_dicts(rows)


# --- MAIN PAGE ---

_ = st.title("💰 Portfolio Snapshot")

fund_info = load_fund_info()

# Dynamic account discovery
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

        if is_ira:
            df = load_ira_summary(latest_file)
        else:
            df = load_401k_summary(latest_file, account_dir.replace("_", " "))

        if df is not None:
            all_holdings.append(df)

if not all_holdings:
    _ = st.warning("No summary data found.")
else:
    raw_combined = pl.concat(all_holdings)

    # Expand based on user mappings
    combined_df = expand_holdings(raw_combined, fund_info)

    total_value: float = float(combined_df.select(pl.col("value").sum()).item())  # type: ignore

    col1, col2, col3 = st.columns(3)
    _ = col1.metric("Total Net Worth", f"${total_value:,.2f}")
    _ = col2.metric("Latest 401K Update", latest_dates.get("401K", "N/A"))
    _ = col3.metric("Latest IRA Update", latest_dates.get("IRA", "N/A"))

    _ = st.divider()

    _ = st.header("📊 Holdings Breakdown")
    agg_dim = st.radio(
        "Aggregate by:", ["Account", "Asset Class", "Investment"], horizontal=True
    )

    mapping = {
        "Account": "account",
        "Asset Class": "asset_class",
        "Investment": "investment",
    }
    group_col = mapping[agg_dim]

    summary_table = (
        combined_df.group_by(group_col)
        .agg(
            [
                pl.col("value").sum().alias("Total Value"),
                (pl.col("value").sum() / total_value * 100).alias("% of Portfolio"),
            ]
        )
        .sort("Total Value", descending=True)
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        pdf = summary_table.to_pandas()
        _ = st.dataframe(
            pdf.style.format({"Total Value": "${:,.2f}", "% of Portfolio": "{:.2f}%"}),
            use_container_width=True,
            hide_index=True,
        )
    with c2:
        # Create a pie chart using Altair
        chart = (
            alt.Chart(pdf)
            .mark_arc(innerRadius=0)
            .encode(
                theta=alt.Theta(field="Total Value", type="quantitative"),
                color=alt.Color(
                    field=group_col, type="nominal", legend=alt.Legend(title=agg_dim)
                ),
                tooltip=[group_col, "Total Value", "% of Portfolio"],
            )
            .properties(height=400)
        )

        _ = st.altair_chart(chart, use_container_width=True)

    _ = st.divider()
    with st.expander("🔍 View All Calculated Allocations"):
        _ = st.dataframe(combined_df.to_pandas(), use_container_width=True)
