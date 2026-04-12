import altair as alt
import polars as pl
import streamlit as st

from data_utils import expand_holdings, get_all_holdings, load_fund_info

# --- MAIN PAGE ---

_ = st.title("💰 Portfolio Snapshot")

fund_info = load_fund_info()

# Load all holdings
raw_combined, latest_dates = get_all_holdings()

if raw_combined.is_empty():
    _ = st.warning("No summary data found.")
else:
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
