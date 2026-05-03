from typing import cast

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
        selection = st.dataframe(
            pdf.style.format({"Total Value": "${:,.2f}", "% of Portfolio": "{:.2f}%"}),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
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

    selected_rows = selection.get("selection", {}).get("rows", [])
    if agg_dim == "Account" and selected_rows:
        selected_index = int(selected_rows[0])
        # The column name in the summary table matches the group_col ('account')
        selected_account_val = cast(object, pdf.iloc[selected_index]["account"])
        selected_account: str = str(selected_account_val)

        st.subheader(f"📂 Account Summary: {selected_account}")

        # Filter for the selected account
        acc_df = combined_df.filter(pl.col("account") == selected_account)
        acc_total = cast(float, acc_df.select(pl.col("value").sum()).item())

        # Group by investment and asset class
        # Note: If multiple rows exist for the same investment (due to expansion),
        # we check if any of them were marked as composite.
        acc_summary = (
            acc_df.group_by(["investment"])
            .agg(
                [
                    pl.col("asset_class").first(),
                    pl.col("value").sum().alias("Value"),
                    pl.col("is_composite").any().alias("is_comp"),
                ]
            )
            .with_columns(
                (pl.col("Value") / acc_total * 100).alias("% of Account"),
                pl.when(pl.col("is_comp"))
                .then(pl.lit("Composite Fund"))
                .otherwise(pl.col("asset_class"))
                .alias("Asset Class"),
            )
            .rename({"investment": "Investment"})
            .sort("Value", descending=True)
        )

        st.dataframe(
            acc_summary.select(["Investment", "Asset Class", "Value", "% of Account"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Value": st.column_config.NumberColumn("Value", format="$%,.2f"),
                "% of Account": st.column_config.NumberColumn(
                    "% of Account", format="%.2f%%"
                ),
            },
        )

    _ = st.divider()

    # --- Metrics Note ---
    try:
        import numpy as np

        returns_df = pl.read_csv("data/asset_classes/returns.csv")
        correlation_df = pl.read_csv("data/asset_classes/correlation.csv")

        asset_classes: list[str] = returns_df["Asset Class"].to_list()

        # Calculate weights for known asset classes
        portfolio_agg = combined_df.group_by("asset_class").agg(pl.col("value").sum())
        known_portfolio = portfolio_agg.filter(
            pl.col("asset_class").is_in(asset_classes)
        )

        known_total = float(known_portfolio.select(pl.col("value").sum()).item() or 0.0)

        if known_total > 0:
            weights_dict = {
                str(cast(object, row["asset_class"])): float(cast(float, row["value"]))
                / known_total
                for row in known_portfolio.to_dicts()
            }

            mu_dicts = returns_df.select(["Asset Class", "Expected Return"]).to_dicts()
            mu_dict = {
                str(cast(object, d["Asset Class"])): float(
                    cast(float, d["Expected Return"])
                )
                for d in mu_dicts
            }

            sigmas_dicts = returns_df.select(
                ["Asset Class", "Standard Deviation"]
            ).to_dicts()
            sigmas_dict = {
                str(cast(object, d["Asset Class"])): float(
                    cast(float, d["Standard Deviation"])
                )
                for d in sigmas_dicts
            }

            # Expected Return
            expected_return = sum(
                float(weights_dict.get(ac, 0.0)) * float(mu_dict.get(ac, 0.0))
                for ac in asset_classes
            )

            # Risk (Standard Deviation)
            W = np.array([float(weights_dict.get(ac, 0.0)) for ac in asset_classes])
            S = np.array([float(sigmas_dict.get(ac, 0.0)) for ac in asset_classes])
            # Reconstruct Covariance
            # Skip first column of correlation_df as it's the index
            R = correlation_df.select(asset_classes).to_numpy()
            cov = np.outer(S, S) * R
            portfolio_risk = float(cast(float, np.sqrt(cast(float, W.T @ cov @ W))))

            st.info(
                f"**Portfolio Projection Summary:** "
                f"Current Expected Return: **{expected_return:.2%}** | "
                f"Current Risk (Std Dev): **{portfolio_risk:.2%}**"
            )
    except Exception:
        # Silently fail if metrics files are missing or incomplete
        pass

    with st.expander("🔍 View All Calculated Allocations"):
        _ = st.dataframe(combined_df.to_pandas(), use_container_width=True)
