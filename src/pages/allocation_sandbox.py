from typing import cast

import altair as alt
import cvxpy as cp
import numpy as np
import pandas as pd
import polars as pl
import streamlit as st
from pypfopt import EfficientFrontier, risk_models

from data_utils import (
    expand_holdings,
    get_account_menus,
    get_account_summaries,
    get_all_holdings,
    load_fund_info,
)


def load_asset_metrics() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Loads returns and correlations from data/asset_classes/."""
    returns_df = pl.read_csv("data/asset_classes/returns.csv")
    correlation_df = pl.read_csv("data/asset_classes/correlation.csv")
    return returns_df, correlation_df


def get_current_allocation(
    combined_df: pl.DataFrame, asset_classes: list[str]
) -> dict[str, float]:
    """Calculates current portfolio weights for known asset classes."""
    portfolio_agg = combined_df.group_by("asset_class").agg(pl.col("value").sum())
    known_portfolio = portfolio_agg.filter(pl.col("asset_class").is_in(asset_classes))
    # Cast Any to known type immediately
    item_val = cast(float | None, known_portfolio.select(pl.col("value").sum()).item())
    total_known_value = float(item_val) if item_val is not None else 0.0

    if total_known_value == 0:
        return dict.fromkeys(asset_classes, 0.0)

    weights = known_portfolio.with_columns(
        (pl.col("value") / total_known_value).alias("weight")
    )

    weights_dict = dict(zip(weights["asset_class"], weights["weight"], strict=True))
    return {
        str(ac): float(cast(float, weights_dict.get(ac, 0.0))) for ac in asset_classes
    }


# --- MAIN PAGE ---

st.title("🏖️ Asset Allocation Sandbox")

fund_info = load_fund_info()
raw_combined, latest_dates = get_all_holdings()

if raw_combined.is_empty():
    st.warning(
        "No summary data found. Please ensure your CSV files are in data/summaries/."
    )
else:
    try:
        returns_df, correlation_df = load_asset_metrics()
        combined_df = expand_holdings(raw_combined, fund_info)

        # 1. Prepare data for PyPortfolioOpt
        # Ensure asset_classes are strings from the start
        asset_classes: list[str] = returns_df["Asset Class"].to_list()
        mu_pd = returns_df.select(["Asset Class", "Expected Return"]).to_pandas()
        mu = mu_pd.set_index("Asset Class")["Expected Return"]

        sigmas_pd = returns_df.select(["Asset Class", "Standard Deviation"]).to_pandas()
        sigmas = sigmas_pd.set_index("Asset Class")["Standard Deviation"]

        # Reconstruct Covariance Matrix from Correlation and Sigma
        corr_matrix = correlation_df.to_pandas().set_index(correlation_df.columns[0])
        # Ensure alignment
        corr_matrix = corr_matrix.loc[asset_classes, asset_classes]
        # Use corr_to_cov
        cov_matrix = risk_models.corr_to_cov(corr_matrix, sigmas)

        # 2. Get Current Allocation
        current_weights = get_current_allocation(combined_df, asset_classes)
        current_exp_return = sum(
            current_weights.get(ac, 0.0) * mu.loc[ac] for ac in asset_classes
        )

        # Calculate current risk
        W_curr = np.array([current_weights.get(ac, 0.0) for ac in asset_classes])
        # cov_matrix is a DataFrame, use its values
        current_risk = float(np.sqrt(W_curr.T @ cov_matrix.values @ W_curr))

        # 3. Optimization Sandbox
        st.subheader("Optimization Parameters")

        # Display Assumptions for transparency
        with st.expander("👁️ View Input Assumptions (Expected Return & Risk)"):
            st.dataframe(
                returns_df.sort("Expected Return", descending=True)
                .to_pandas()
                .style.format(
                    {"Expected Return": "{:.2%}", "Standard Deviation": "{:.2%}"}
                ),
                hide_index=True,
                use_container_width=True,
            )

        col_left, col_right = st.columns(2)

        # Optimization Goal Selection
        with col_left:
            opt_goal = st.radio(
                "Optimization Goal",
                ["Minimize Risk for Target Return", "Maximize Return for Target Risk"],
                help="Choose whether you want to set a specific return target or a specific risk level.",
            )

        # Avoid reportAny by casting result of min/max
        min_ret = float(cast(float, mu.min()))
        max_ret = float(cast(float, mu.max()))
        min_risk = float(cast(float, sigmas.min()))
        max_risk = float(cast(float, sigmas.max()))

        # Initialize session state for sliders
        if "target_return_val" not in st.session_state:
            st.session_state.target_return_val = max(
                min_ret, min(max_ret, current_exp_return)
            )
        if "target_risk_val" not in st.session_state:
            st.session_state.target_risk_val = max(
                min_risk, min(max_risk, current_risk)
            )

        with col_left:
            if opt_goal == "Minimize Risk for Target Return":
                target_val = st.slider(
                    "Target Expected Return",
                    min_value=min_ret,
                    max_value=max_ret,
                    value=st.session_state.target_return_val,
                    format="%.3f",
                    step=0.001,
                )
                st.session_state.target_return_val = target_val
            else:
                target_val = st.slider(
                    "Target Portfolio Risk (Std Dev)",
                    min_value=min_risk,
                    max_value=max_risk,
                    value=st.session_state.target_risk_val,
                    format="%.3f",
                    step=0.001,
                )
                st.session_state.target_risk_val = target_val

        with col_right:
            min_weight = (
                st.slider(
                    "Minimum Allocation per Asset (%)",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.5,
                )
                / 100.0
            )

        st.write("---")
        st.write("**Account-Level Constraints**")
        use_account_constraints = st.toggle(
            "Respect Account Boundaries & Menus",
            value=False,
            help="Enforce that allocations must be achievable given fixed account balances and limited fund menus in each account.",
        )

        # 4. Calculate Optimal Allocation for target return
        ef = EfficientFrontier(mu, cov_matrix)

        if min_weight > 0:

            def min_weight_cons(w: cp.Variable) -> object:
                return w >= min_weight

            ef.add_constraint(min_weight_cons)

        # Variables for account constraints
        weights_matrix: cp.Variable | None = None
        acc_list: list[str] = []
        acc_menus: dict[str, dict[str, list[str]]] = {}
        acc_summaries = pl.DataFrame()

        if use_account_constraints:
            acc_summaries = get_account_summaries()
            acc_menus = get_account_menus(fund_info)

            total_sum_val = cast(float | None, acc_summaries["value"].sum())
            total_portfolio_value = (
                float(total_sum_val) if total_sum_val is not None else 0.0
            )

            # Account budget shares (b_i)
            budgets: dict[str, float] = {
                str(row["account"]): float(cast(float, row["value"]))
                / total_portfolio_value
                for row in cast(list[dict[str, object]], acc_summaries.to_dicts())
            }

            # Decision variables: x[acc][asset] is weight of asset in account acc
            n_assets = len(asset_classes)
            acc_list = list(budgets.keys())
            n_acc = len(acc_list)

            # Create a matrix of variables for each account/asset pair
            wm = cp.Variable((n_acc, n_assets), nonneg=True)
            weights_matrix = wm

            # 1. Account budget constraints
            for idx, acc in enumerate(acc_list):
                b = budgets[acc]

                def budget_cons(w: cp.Variable, i: int = idx, val: float = b) -> object:
                    return cp.sum(wm[i, :]) == val

                ef.add_constraint(budget_cons)

            # 2. Availability constraints
            globally_reachable = set()
            for idx, acc in enumerate(acc_list):
                menu = acc_menus.get(acc, {})
                for jdx, asset in enumerate(asset_classes):
                    if menu and asset not in menu:

                        def avail_cons(
                            w: cp.Variable, i: int = idx, j: int = jdx
                        ) -> object:
                            return wm[i, j] == 0

                        ef.add_constraint(avail_cons)
                    else:
                        globally_reachable.add(asset)

            # 3. Link to global weights: w[j] == sum(weights_matrix[:, j])
            def link_cons(w: cp.Variable) -> object:
                return w == cp.sum(wm, axis=0)

            ef.add_constraint(link_cons)

            unreachable = [a for a in asset_classes if a not in globally_reachable]
            if unreachable:
                st.warning(
                    f"Note: These asset classes are not available in any of your account menus: {', '.join(unreachable)}"
                )

        try:
            # Optimize based on chosen goal
            if opt_goal == "Minimize Risk for Target Return":
                optimal_weights_raw = ef.efficient_return(target_val)
                target_desc = f"{target_val:.2%} Return"
            else:
                optimal_weights_raw = ef.efficient_risk(target_val)
                target_desc = f"{target_val:.2%} Risk"

            # Ensure keys are strings
            optimal_weights: dict[str, float] = {
                str(k): float(v) for k, v in optimal_weights_raw.items()
            }

            # Performance of optimal portfolio
            ret, risk, sharpe = ef.portfolio_performance(risk_free_rate=0.04)

            # 5. Display Comparison
            st.divider()
            st.subheader(
                f"Comparison: Current vs. Optimal Allocation for {target_desc}"
            )

            col1, col2 = st.columns(2)
            if opt_goal == "Minimize Risk for Target Return":
                # User set return, show resulting risk
                col1.metric("Optimal Portfolio Risk (Std Dev)", f"{risk:.2%}")
            else:
                # User set risk, show resulting return
                col1.metric("Optimal Portfolio Expected Return", f"{ret:.2%}")

            col2.metric(
                "Optimal Portfolio Sharpe Ratio",
                f"{sharpe:.2f}",
                help="Assumes 4% risk-free rate",
            )

            # Create comparison dataframe
            comparison_data = []
            for ac in asset_classes:
                curr_w = float(current_weights.get(ac, 0.0))
                opt_w = float(optimal_weights.get(ac, 0.0))
                comparison_data.append(
                    {
                        "Asset Class": ac,
                        "Current (%)": curr_w * 100,
                        "Optimal (%)": opt_w * 100,
                        "Difference (%)": (opt_w - curr_w) * 100,
                    }
                )

            comparison_df = pd.DataFrame(comparison_data)

            st.dataframe(
                comparison_df.style.format(
                    {
                        "Current (%)": "{:.2f}%",
                        "Optimal (%)": "{:.2f}%",
                        "Difference (%)": "{:+.2f}%",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

            # 6. Visual Comparison
            chart_df = comparison_df.melt(
                id_vars="Asset Class",
                value_vars=["Current (%)", "Optimal (%)"],
                var_name="Allocation Type",
                value_name="Percentage",
            )

            chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X("Allocation Type:N", title=None),
                    y=alt.Y("Percentage:Q", title="Allocation (%)"),
                    color="Allocation Type:N",
                    column=alt.Column(
                        "Asset Class:N",
                        title="Asset Class",
                        header=alt.Header(labelOrient="bottom", labelPadding=10),
                    ),
                )
                .properties(width=100, height=300)
            )

            st.altair_chart(chart)

            # 7. Recommended Transactions
            st.divider()
            st.subheader("📝 Recommended Transactions")

            transactions = []
            if (
                use_account_constraints
                and weights_matrix is not None
                and weights_matrix.value is not None
            ):
                # Per-account, per-asset optimization was performed
                opt_matrix_obj: object = weights_matrix.value

                item_total_val = cast(
                    float | None, combined_df.select(pl.col("value").sum()).item()
                )
                total_val = float(item_total_val) if item_total_val is not None else 0.0

                # Current values per account/asset
                curr_vals = combined_df.group_by(["account", "asset_class"]).agg(
                    pl.col("value").sum()
                )

                # To find specific funds currently held:
                current_holdings = combined_df.select(
                    ["account", "asset_class", "investment", "value"]
                )

                for idx, acc in enumerate(acc_list):
                    menu = acc_menus.get(acc, {})
                    for jdx, asset in enumerate(asset_classes):
                        # Use cast(Any, ...) only if absolutely necessary, but let's try to be safer
                        val_at_idx = cast(list[list[float]], opt_matrix_obj)[idx][jdx]
                        target_val = float(val_at_idx) * total_val

                        # Find current total for this asset class in this account
                        match = curr_vals.filter(
                            (pl.col("account") == acc)
                            & (pl.col("asset_class") == asset)
                        )
                        # Safer extraction: sum of value column (0 if empty)
                        current_total_val = float(
                            match.select(pl.col("value")).sum().item() or 0.0
                        )

                        delta = target_val - current_total_val
                        if abs(delta) > 1.0:
                            action = "BUY" if delta > 0 else "SELL"

                            # Identify specific funds
                            funds_str = ""
                            if action == "SELL":
                                # List existing funds in this asset class
                                held = current_holdings.filter(
                                    (pl.col("account") == acc)
                                    & (pl.col("asset_class") == asset)
                                )
                                funds_str = ", ".join(
                                    [
                                        str(f)
                                        for f in cast(
                                            list[object], held["investment"].to_list()
                                        )
                                    ]
                                )
                            else:
                                # List available funds from menu
                                available_funds = menu.get(asset, [])
                                if available_funds:
                                    funds_str = ", ".join(available_funds)
                                else:
                                    # This might happen if an asset class is allowed but no specific fund is mapped yet
                                    funds_str = (
                                        "No specific fund found in options mapping"
                                    )

                            transactions.append(
                                {
                                    "Account": acc,
                                    "Asset Class": asset,
                                    "Action": action,
                                    "Amount": abs(delta),
                                    "Funds": funds_str,
                                }
                            )
            else:
                # Global optimization only
                total_val = float(
                    combined_df.select(pl.col("value").sum()).item() or 0.0
                )
                curr_vals_global = combined_df.group_by("asset_class").agg(
                    pl.col("value").sum()
                )

                for asset in asset_classes:
                    target_val = optimal_weights.get(asset, 0.0) * total_val

                    match = curr_vals_global.filter(pl.col("asset_class") == asset)
                    current_val = float(
                        match.select(pl.col("value")).sum().item() or 0.0
                    )

                    delta = target_val - current_val
                    if abs(delta) > 1.0:
                        transactions.append(
                            {
                                "Account": "Global (Aggregated)",
                                "Asset Class": asset,
                                "Action": "BUY" if delta > 0 else "SELL",
                                "Amount": abs(delta),
                                "Funds": "N/A (Enable Account Constraints for details)",
                            }
                        )

            if transactions:
                trans_df = pd.DataFrame(transactions)

                # Sort to ensure SELLs come before BUYs within each account for the running balance
                trans_df = trans_df.sort_values(
                    ["Account", "Action"], ascending=[True, False]
                )

                def calc_cash_flow(row: pd.Series) -> float:
                    amt = float(cast(float, row["Amount"]))
                    return amt if cast(str, row["Action"]) == "SELL" else -amt

                # Calculate Cash Flow per transaction
                # SELL generates cash (+), BUY consumes cash (-)
                trans_df["Cash Flow"] = trans_df.apply(calc_cash_flow, axis=1)

                # Calculate Running Balance per Account
                trans_df["Running Balance"] = trans_df.groupby("Account")[
                    "Cash Flow"
                ].cumsum()

                # Drop the helper column
                display_df = trans_df.drop(columns=["Cash Flow"])

                st.dataframe(
                    display_df.style.format(
                        {"Amount": "${:,.2f}", "Running Balance": "${:,.2f}"}
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("Portfolio is already aligned with the optimal allocation.")

        except Exception as e:
            st.error(f"Could not find an optimal allocation for the target return: {e}")

        with st.expander("📝 About this optimization"):
            st.markdown("""
            **Methodology:**
            - This sandbox uses the **Mean-Variance Optimization (MVO)** framework, also known as the Markowitz Efficient Frontier.
            - It calculates the asset allocation that **minimizes portfolio variance (risk)** for a specific **target expected return**.
            - Asset class assumptions (expected returns, standard deviations, and correlations) are loaded from `data/asset_classes/`.
            - The current allocation is calculated from your holdings, normalized to include only the known asset classes used in the model.

            **Advanced Constraints:**
            - **Minimum Allocation:** Ensures every asset class is represented by at least a small percentage.
            - **Account Boundaries & Menus:** This is a complex linear constraint. It acknowledges that your portfolio is not one big bucket, but several smaller buckets (accounts) with fixed sizes. Furthermore, it respects that each account can only hold specific investments. The optimizer finds the best *achievable* global allocation by finding a valid sub-allocation for every individual account.
            """)

    except FileNotFoundError:
        st.error(
            "Required asset class metric files not found in `data/asset_classes/`."
        )
    except Exception as e:
        st.error(f"An error occurred: {e}")
