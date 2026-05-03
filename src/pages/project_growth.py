from typing import cast

import altair as alt
import cvxpy as cp
import numpy as np
import pandas as pd
import polars as pl
import streamlit as st

from data_utils import (
    FundInfo,
    get_account_menus,
    get_all_holdings,
    load_fund_info,
)


def load_asset_metrics():
    """Loads returns and correlations from data/asset_classes/."""
    try:
        returns_df = pl.read_csv("data/asset_classes/returns.csv")
        correlation_df = pl.read_csv("data/asset_classes/correlation.csv")
        return returns_df, correlation_df
    except FileNotFoundError:
        st.error(
            "Required asset class metric files not found in `data/asset_classes/`. Please ensure `returns.csv` and `correlation.csv` exist."
        )
        return None, None


def solve_mvo(
    target_return: float,
    returns: np.ndarray,
    cov: np.ndarray,
    account_weights: dict[str, float] | None = None,
    account_capabilities: dict[str, list[int]] | None = None,
) -> tuple[np.ndarray | None, float]:
    """
    Solves Mean-Variance Optimization to minimize risk for a target return.
    If the target return is infeasible, it finds the maximum possible return first.
    Returns (weights, implicit_std_dev).
    """
    n_assets = len(returns)
    w = cp.Variable(n_assets)

    # Base constraints
    base_constraints: list[cp.Constraint] = [
        cast(cp.Constraint, cp.sum(w) == 1),
        cast(cp.Constraint, w >= 0),
    ]

    # Account-level logic
    if account_weights and account_capabilities:
        account_vars = {
            acc: cp.Variable(n_assets) for acc in account_capabilities.keys()
        }
        weighted_vars = []
        for acc, w_a in account_vars.items():
            f_a = account_weights.get(acc, 0.0)
            weighted_vars.append(f_a * w_a)
            base_constraints.append(cast(cp.Constraint, cp.sum(w_a) == 1))
            base_constraints.append(cast(cp.Constraint, w_a >= 0))
            unavailable_indices = [
                i for i in range(n_assets) if i not in account_capabilities[acc]
            ]
            if unavailable_indices:
                base_constraints.append(
                    cast(cp.Constraint, w_a[unavailable_indices] == 0)
                )
        base_constraints.append(cast(cp.Constraint, w == cp.sum(weighted_vars)))

    # Phase 1: Check Feasibility / Find Max Possible Return
    max_ret_prob = cp.Problem(
        cp.Maximize(cast(cp.Expression, returns @ w)), base_constraints
    )
    try:
        max_ret_prob.solve()
        w_val = w.value
        if w_val is None:
            return None, 0.0
        max_possible = float(returns @ w_val)
    except Exception:
        return None, 0.0

    # Adjust target if unreachable
    actual_target = min(target_return, max_possible)

    # Phase 2: Minimize Variance
    prob_val = cp.quad_form(w, cov)
    objective = cp.Minimize(cast(cp.Expression, prob_val))
    constraints = base_constraints + [cast(cp.Constraint, returns @ w >= actual_target)]

    problem = cp.Problem(objective, constraints)
    try:
        problem.solve()
        # Access value safely for typing
        weights_val = w.value
        if weights_val is None:
            return None, 0.0
        weights = cast(np.ndarray, np.array(cast(object, weights_val)).flatten())
        # Ensure weights sum to 1 exactly (cleaning floating point noise)
        weights = cast(np.ndarray, weights / np.sum(weights))
        portfolio_std_dev = float(
            cast(float, np.sqrt(cast(float, weights.T @ cov @ weights)))
        )
        return weights, portfolio_std_dev
    except Exception:
        return None, 0.0


def run_simulation(
    initial_value: float,
    account_values: dict[str, float],
    contributions: dict[str, float],
    target_return: float,
    inflation_rate: float,
    years: int,
    rebalance_quarterly: bool,
    respect_constraints: bool,
    returns_df: pl.DataFrame,
    correlation_df: pl.DataFrame,
    account_menus: dict[str, dict[str, list[str]]],
    n_paths: int = 500,
):
    # 1. Prepare asset metrics
    asset_names: list[str] = returns_df["Asset Class"].to_list()
    mu = returns_df["Expected Return"].to_numpy()
    sigmas = returns_df["Standard Deviation"].to_numpy()
    rho = correlation_df.select(asset_names).to_numpy()
    cov = np.outer(sigmas, sigmas) * rho

    # Map asset names to indices
    asset_to_idx = {str(name): i for i, name in enumerate(asset_names)}

    # 2. Map account capabilities to indices
    account_capabilities = {}
    if respect_constraints:
        for acc in account_values.keys():
            menu = account_menus.get(acc, {})
            indices = []
            for asset_class in menu.keys():
                if asset_class in asset_to_idx:
                    indices.append(asset_to_idx[asset_class])

            # CRITICAL FIX: If an account has weight but no recognized capabilities,
            # we MUST allow at least one asset or all assets to avoid infeasibility.
            if not indices:
                indices = list(range(len(asset_names)))

            account_capabilities[acc] = indices

    # 3. Initial Weights
    account_weights = {acc: val / initial_value for acc, val in account_values.items()}

    # 4. Solve for optimal weights W
    W_raw, portfolio_std_dev_raw = solve_mvo(
        target_return,
        mu,
        cov,
        account_weights if respect_constraints else None,
        account_capabilities if respect_constraints else None,
    )
    W: np.ndarray | None = W_raw
    portfolio_std_dev: float = portfolio_std_dev_raw

    if W is None:
        msg = "Unable to find a valid allocation. "
        if respect_constraints:
            msg += "This usually happens if account constraints are too restrictive for the target return."
        else:
            msg += "Check if your target return is within the range of your asset class metrics."
        return None, 0.0, 0.0, msg

    achieved_return = float(mu @ W)

    # 5. Run Simulation
    # Frequency handling
    steps_per_year = 4 if rebalance_quarterly else 1
    dt = 1 / steps_per_year
    total_steps = years * steps_per_year

    # Sample returns for all paths and steps
    mu_dt = (1 + mu) ** dt - 1
    cov_dt = cov * dt

    # Sample returns (Multivariate Normal)
    all_sampled_returns = np.random.multivariate_normal(
        mu_dt, cov_dt, size=(n_paths, total_steps)
    )

    # Initialize balances
    balances = np.zeros((n_paths, total_steps + 1))
    balances[:, 0] = initial_value

    # Current annual contribution
    current_yearly_contributions = np.array(
        [contributions.get(acc, 0.0) for acc in account_values]
    )

    for step in range(total_steps):
        year = step // steps_per_year
        is_year_start = (step % steps_per_year) == 0

        # Add contributions at start of each year
        if is_year_start:
            annual_total = np.sum(
                current_yearly_contributions * ((1 + inflation_rate) ** year)
            )
            balances[:, step] += annual_total

        # Calculate portfolio return for this step
        step_returns = all_sampled_returns[:, step, :]  # paths x assets
        portfolio_returns = step_returns @ W  # paths

        balances[:, step + 1] = balances[:, step] * (1 + portfolio_returns)

    return balances, achieved_return, portfolio_std_dev, None


# --- UI ---

st.title("📈 Projected Growth Simulation")
st.write(
    "Visualize the potential growth of your portfolio using Monte-Carlo simulations based on Mean-Variance Optimization."
)

returns_df, correlation_df = load_asset_metrics()

if returns_df is not None and correlation_df is not None:
    # 1. Prepare global bounds
    min_ret = float(cast(float, returns_df["Expected Return"].min()))
    max_ret = float(cast(float, returns_df["Expected Return"].max()))

    # 2. Get Current Portfolio Status
    fund_info = load_fund_info()
    raw_combined, _ = get_all_holdings()
    account_menus = get_account_menus(fund_info)

    if raw_combined.is_empty():
        st.warning("No portfolio data found. Please ensure your summaries are loaded.")
        initial_value = 100000.0
        account_values = {"Default": 100000.0}
        current_exp_return = (min_ret + max_ret) / 2
    else:
        account_values_dicts = (
            raw_combined.group_by("account").agg(pl.col("value").sum()).to_dicts()
        )
        account_values = {
            str(cast(object, d["account"])): float(cast(float, d["value"]))
            for d in account_values_dicts
        }
        initial_value = sum(account_values.values())

        # Compute current expected return
        total_value = initial_value
        weighted_return = 0.0
        average_ret = float(cast(float, returns_df["Expected Return"].mean()))
        for row in raw_combined.to_dicts():
            fund = fund_info.get(str(cast(object, row["investment"])), FundInfo())
            if fund.asset_class:
                filtered = returns_df.filter(pl.col("Asset Class") == fund.asset_class)
                exp_ret = (
                    average_ret
                    if filtered.is_empty()
                    else float(cast(float, filtered["Expected Return"].item()))
                )
                weighted_return += (
                    float(cast(float, row["value"])) / total_value
                ) * exp_ret
        current_exp_return = weighted_return

    # Sidebar / Settings
    st.sidebar.header("Simulation Settings")
    years = st.sidebar.slider("Time Horizon (Years)", 1, 50, 20)
    inflation_rate = (
        st.sidebar.slider("Contribution Inflation Rate (%)", 0.0, 10.0, 3.0) / 100.0
    )
    n_paths = 500

    st.subheader("Assumptions")
    col1, col2 = st.columns(2)

    with col1:
        min_ret = float(cast(float, returns_df["Expected Return"].min()))
        max_ret = float(cast(float, returns_df["Expected Return"].max()))

        # Robust session state handling for the slider default
        if "target_return_pct_slider" not in st.session_state:
            st.session_state.target_return_pct_slider = float(current_exp_return * 100)

        target_return_pct = st.slider(
            "Target Annual Return",
            min_ret * 100,
            max_ret * 100,
            key="target_return_pct_slider",
            format="%.1f%%",
            step=0.1,
        )
        target_return = target_return_pct / 100
        rebalance_quarterly = st.toggle(
            "Quarterly Rebalancing", value=True, help="If False, rebalances annually."
        )
        respect_constraints = st.toggle(
            "Respect Account Constraints",
            value=True,
            help="If enabled, optimization is restricted by the funds available in each account.",
        )

    with col2:
        st.write("**Annual Contributions per Account**")

        # Create a stable list of accounts for initialization
        current_accounts = sorted(account_values.keys())

        # Initialize baseline dataframe ONLY ONCE if not present
        if "baseline_contrib_df" not in st.session_state:
            st.session_state.baseline_contrib_df = pd.DataFrame(
                [
                    {"Account": acc, "Annual Contribution ($)": 0}
                    for acc in current_accounts
                ]
            )

        # Sync baseline if the set of accounts actually changed
        current_acc_set = set(current_accounts)
        baseline_acc_set = set(st.session_state.baseline_contrib_df["Account"])
        if current_acc_set != baseline_acc_set:
            old_data = {
                str(cast(object, r["Account"])): int(
                    cast(float, r["Annual Contribution ($)"])
                )
                for _, r in st.session_state.baseline_contrib_df.iterrows()
            }
            st.session_state.baseline_contrib_df = pd.DataFrame(
                [
                    {"Account": acc, "Annual Contribution ($)": old_data.get(acc, 0)}
                    for acc in current_accounts
                ]
            )

        # Call the editor with the baseline. Streamlit's internal widget state
        # (via the key) will handle preserving user edits across reruns.
        # We do NOT update st.session_state.baseline_contrib_df here.
        final_contrib_df = st.data_editor(
            st.session_state.baseline_contrib_df,
            column_config={
                "Account": st.column_config.TextColumn("Account", disabled=True),
                "Annual Contribution ($)": st.column_config.NumberColumn(
                    "Annual Contribution ($)",
                    min_value=0,
                    step=1000,
                    format="$%,d",
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="annual_contrib_editor_widget",
        )

        # Use the return value directly for the simulation
        contributions = {
            str(cast(object, row["Account"])): float(
                cast(float, row["Annual Contribution ($)"])
            )
            for _, row in final_contrib_df.iterrows()
        }

    if st.button("Run Simulation", type="primary"):
        with st.spinner("Running 500 simulations..."):
            balances, ach_ret, imp_risk, error = run_simulation(
                initial_value,
                account_values,
                contributions,
                target_return,
                inflation_rate,
                years,
                rebalance_quarterly,
                respect_constraints,
                returns_df,
                correlation_df,
                account_menus,
                n_paths=n_paths,
            )

        if error:
            st.error(error)
        elif balances is not None:
            # Display Optimization Results
            if abs(ach_ret - target_return) > 0.001:
                st.warning(
                    f"Target return of {target_return:.1%} was unreachable. Optimized for maximum possible return: {ach_ret:.2%}"
                )

            st.success(
                f"Simulation complete. Optimized Portfolio Risk (Std Dev): **{imp_risk:.2%}** at **{ach_ret:.2%}** expected return."
            )

            # Prepare data for plotting
            time_steps = np.arange(balances.shape[1])
            if rebalance_quarterly:
                time_years = time_steps / 4
            else:
                time_years = time_steps

            p10 = np.percentile(balances, 10, axis=0)
            p33 = np.percentile(balances, 33, axis=0)
            p50 = np.percentile(balances, 50, axis=0)
            p66 = np.percentile(balances, 66, axis=0)
            p90 = np.percentile(balances, 90, axis=0)

            plot_df = pl.DataFrame(
                {
                    "Year": time_years,
                    "10th": p10,
                    "33rd": p33,
                    "50th": p50,
                    "66th": p66,
                    "90th": p90,
                }
            )

            base = alt.Chart(plot_df).encode(x=alt.X("Year:Q", title="Years"))
            area_90 = base.mark_area(opacity=0.1, color="gray").encode(
                y="10th:Q", y2="90th:Q"
            )
            area_66 = base.mark_area(opacity=0.3, color="steelblue").encode(
                y="33rd:Q", y2="66th:Q"
            )
            line = base.mark_line(color="steelblue", strokeWidth=2).encode(
                y=alt.Y("50th:Q", title="Portfolio Balance ($)")
            )

            st.altair_chart(area_90 + area_66 + line, use_container_width=True)

            st.subheader(f"Projected Balance after {years} Years")
            m1, m2, m3 = st.columns(3)
            m1.metric("33rd Percentile", f"${p33[-1]:,.0f}")
            m2.metric("Median (50th)", f"${p50[-1]:,.0f}")
            m3.metric("66th Percentile", f"${p66[-1]:,.0f}")

            st.info(
                "The shaded regions represent the 10th-90th (light) and 33rd-66th (dark) percentile ranges. "
                "Simulations assume returns are normally distributed and correlated according to historical metrics."
            )
