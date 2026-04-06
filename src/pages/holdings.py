import os

import altair as alt
import polars as pl
import streamlit as st

from data_utils import clean_currency, get_latest_file, load_mappings


# --- LOADING LOGIC ---
def load_401k_summary(file_path: str | None) -> pl.DataFrame | None:
    if not file_path:
        return None
    df = pl.read_csv(file_path, truncate_ragged_lines=True)
    df = df.filter(pl.col("Quantity").is_not_null() & (pl.col("Quantity") != ""))
    df = df.with_columns(
        [
            clean_currency(pl.col("Current balance")).alias("value"),
            clean_currency(pl.col("Quantity")).alias("quantity"),
            pl.lit("401K").alias("type"),
            pl.lit("401K Account").alias("account"),
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


def expand_holdings(
    df: pl.DataFrame, asset_map: dict[str, str], comp_map: dict[str, dict[str, float]]
) -> pl.DataFrame:
    """
    Recursively expand investments into their underlying asset classes.
    """
    rows: list[dict[str, object]] = []

    def process_investment(
        row_dict: dict[str, object], current_investment: str, current_value: float
    ) -> None:
        # 1. Check if fund has explicit composition
        if current_investment in comp_map and comp_map[current_investment]:
            for sub_fund, weight in comp_map[current_investment].items():
                process_investment(row_dict, sub_fund, current_value * weight)
        else:
            # 2. Assign asset class
            # Try to match mapping exactly or by partial string
            ac = "Other/Unclassified"
            for key, val in asset_map.items():
                if key.lower() in current_investment.lower():
                    ac = val
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

asset_class_map: dict[str, str]
fund_compositions: dict[str, dict[str, float]]
symbol_map: dict[str, str]
asset_class_map, fund_compositions, symbol_map = load_mappings()

s_401k_path = get_latest_file("data/summaries/401K")
s_ira_path = get_latest_file("data/summaries/IRA")

df_401k = load_401k_summary(s_401k_path)
df_ira = load_ira_summary(s_ira_path)

all_holdings: list[pl.DataFrame] = []
if df_401k is not None:
    all_holdings.append(df_401k)
if df_ira is not None:
    all_holdings.append(df_ira)

if not all_holdings:
    _ = st.warning("No summary data found.")
else:
    raw_combined = pl.concat(all_holdings)

    # Expand based on user mappings
    combined_df = expand_holdings(raw_combined, asset_class_map, fund_compositions)

    total_value: float = float(combined_df.select(pl.col("value").sum()).item())  # type: ignore

    col1, col2, col3 = st.columns(3)
    _ = col1.metric("Total Net Worth", f"${total_value:,.2f}")
    _ = col2.metric(
        "Latest Update (401K)",
        os.path.basename(s_401k_path).split("_")[0] if s_401k_path else "N/A",
    )
    _ = col3.metric(
        "Latest Update (IRA)",
        os.path.basename(s_ira_path).split("_")[0] if s_ira_path else "N/A",
    )

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
