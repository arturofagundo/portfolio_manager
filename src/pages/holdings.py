import streamlit as st
import polars as pl
import pandas as pd
import os
import glob
from datetime import datetime
import json
import altair as alt
from data_utils import get_latest_file, clean_currency, load_mappings

# --- LOADING LOGIC ---
def load_401k_summary(file_path):
    if not file_path: return None
    df = pl.read_csv(file_path, truncate_ragged_lines=True)
    df = df.filter(pl.col("Quantity").is_not_null() & (pl.col("Quantity") != ""))
    df = df.with_columns([
        clean_currency(pl.col("Current balance")).alias("value"),
        clean_currency(pl.col("Quantity")).alias("quantity"),
        pl.lit("401K").alias("type"),
        pl.lit("401K Account").alias("account"),
        pl.col("Fund name").alias("investment")
    ])
    return df.select(["type", "account", "investment", "value", "quantity"])

def load_ira_summary(file_path):
    if not file_path: return None
    df = pl.read_csv(file_path, truncate_ragged_lines=True)
    df = df.filter(pl.col("Current Value").is_not_null() & (pl.col("Current Value") != ""))
    df = df.with_columns([
        clean_currency(pl.col("Current Value")).alias("value"),
        clean_currency(pl.col("Quantity")).alias("quantity"),
        pl.lit("IRA").alias("type"),
        pl.col("Account Name").alias("account"),
        pl.col("Description").alias("investment")
    ])
    return df.select(["type", "account", "investment", "value", "quantity"])

# --- ALLOCATION LOGIC ---

def expand_holdings(df, asset_map, comp_map):
    """
    Recursively expand investments into their underlying asset classes.
    """
    rows = []
    
    def process_investment(row_dict, current_investment, current_value):
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
            new_row['investment_actual'] = current_investment
            new_row['asset_class'] = ac
            new_row['value'] = current_value
            rows.append(new_row)

    for row in df.to_dicts():
        process_investment(row, row['investment'], row['value'])
        
    return pl.from_dicts(rows)

# --- MAIN PAGE ---

st.title("💰 Portfolio Snapshot")

asset_class_map, fund_compositions = load_mappings()

s_401k_path = get_latest_file("data/summaries/401K")
s_ira_path = get_latest_file("data/summaries/IRA")

df_401k = load_401k_summary(s_401k_path)
df_ira = load_ira_summary(s_ira_path)

all_holdings = []
if df_401k is not None: all_holdings.append(df_401k)
if df_ira is not None: all_holdings.append(df_ira)

if not all_holdings:
    st.warning("No summary data found.")
else:
    raw_combined = pl.concat(all_holdings)
    
    # Expand based on user mappings
    combined_df = expand_holdings(raw_combined, asset_class_map, fund_compositions)

    total_value = combined_df.select(pl.col("value").sum()).item()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Net Worth", f"${total_value:,.2f}")
    col2.metric("Latest Update (401K)", os.path.basename(s_401k_path).split('_')[0] if s_401k_path else "N/A")
    col3.metric("Latest Update (IRA)", os.path.basename(s_ira_path).split('_')[0] if s_ira_path else "N/A")

    st.divider()

    st.header("📊 Holdings Breakdown")
    agg_dim = st.radio("Aggregate by:", ["Account", "Asset Class", "Investment"], horizontal=True)

    mapping = {"Account": "account", "Asset Class": "asset_class", "Investment": "investment"}
    group_col = mapping[agg_dim]
    
    summary_table = (
        combined_df.group_by(group_col)
        .agg([
            pl.col("value").sum().alias("Total Value"),
            (pl.col("value").sum() / total_value * 100).alias("% of Portfolio")
        ])
        .sort("Total Value", descending=True)
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        pdf = summary_table.to_pandas()
        st.dataframe(pdf.style.format({"Total Value": "${:,.2f}", "% of Portfolio": "{:.2f}%"}), use_container_width=True, hide_index=True)
    with c2:
        # Create a pie chart using Altair
        chart = alt.Chart(pdf).mark_arc(innerRadius=0).encode(
            theta=alt.Theta(field="Total Value", type="quantitative"),
            color=alt.Color(field=group_col, type="nominal", legend=alt.Legend(title=agg_dim)),
            tooltip=[group_col, "Total Value", "% of Portfolio"]
        ).properties(height=400)
        
        st.altair_chart(chart, use_container_width=True)

    st.divider()
    with st.expander("🔍 View All Calculated Allocations"):
        st.dataframe(combined_df.to_pandas(), use_container_width=True)
