from typing import cast

import numpy as np
import polars as pl
import streamlit as st

from data_utils import expand_holdings, get_all_holdings, load_fund_info


def load_asset_metrics() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Loads returns and correlations from data/asset_classes/."""
    returns_df = pl.read_csv("data/asset_classes/returns.csv")
    correlation_df = pl.read_csv("data/asset_classes/correlation.csv")
    return returns_df, correlation_df


def calculate_portfolio_metrics(
    combined_df: pl.DataFrame, returns_df: pl.DataFrame, correlation_df: pl.DataFrame
) -> tuple[float, float]:
    """Calculates expected return and standard deviation for the portfolio."""

    # 1. Aggregate portfolio by asset class and calculate weights
    portfolio_agg = combined_df.group_by("asset_class").agg(pl.col("value").sum())
    total_value = cast(float, portfolio_agg.select(pl.col("value").sum()).item())
    portfolio_agg = portfolio_agg.with_columns(
        [(pl.col("value") / total_value).alias("weight")]
    )

    # 2. Align metrics with portfolio asset classes
    # We only care about asset classes that are in the metrics files
    asset_classes = returns_df["Asset Class"].to_list()

    # Filter portfolio to only include known asset classes (or handle unknown)
    # For now, we'll ignore "Other/Unclassified" or warn the user
    known_portfolio = portfolio_agg.filter(pl.col("asset_class").is_in(asset_classes))
    known_value = cast(float, known_portfolio.select(pl.col("value").sum()).item())

    unclassified_ratio = (total_value - known_value) / total_value
    if unclassified_ratio >= 0.0005:  # Only warn if it's at least 0.1% when rounded
        st.warning(
            f"Some assets ({unclassified_ratio:.1%} of portfolio) "
            "are in unclassified or unknown asset classes and are excluded from metrics."
        )

    # Re-calculate weights based on known assets for metric calculation
    known_portfolio = known_portfolio.with_columns(
        [(pl.col("value") / known_value).alias("weight")]
    )

    # 3. Calculate Expected Return
    # E[Rp] = sum(wi * Ri)
    metrics = known_portfolio.join(
        returns_df, left_on="asset_class", right_on="Asset Class"
    )
    expected_return = (metrics["weight"] * metrics["Expected Return"]).sum()

    # 4. Calculate Portfolio Standard Deviation
    # Sigma_p = sqrt( W^T * Cov * W )
    # Cov(i,j) = rho(i,j) * sigma(i) * sigma(j)

    # Create weight vector aligned with correlation matrix order
    # The correlation matrix columns (excluding the first one which is names)
    corr_assets = correlation_df.columns[1:]
    weights_dict = dict(zip(metrics["asset_class"], metrics["weight"], strict=True))
    w = np.array([weights_dict.get(a, 0.0) for a in corr_assets])

    # Create standard deviation vector
    sigmas_dict = dict(
        zip(returns_df["Asset Class"], returns_df["Standard Deviation"], strict=True)
    )
    sigmas = np.array([sigmas_dict.get(a, 0.0) for a in corr_assets])

    # Correlation matrix
    rho = correlation_df.select(corr_assets).to_numpy()

    # Covariance matrix: Cov = diag(sigmas) * rho * diag(sigmas)
    cov = np.outer(sigmas, sigmas) * rho

    # Portfolio variance: w^T * cov * w
    portfolio_variance = w.T @ cov @ w
    portfolio_std_dev = np.sqrt(portfolio_variance)

    return float(expected_return), float(portfolio_std_dev)


# --- MAIN PAGE ---

st.title("📈 Portfolio Performance Metrics")

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

        exp_return, std_dev = calculate_portfolio_metrics(
            combined_df, returns_df, correlation_df
        )

        # Display Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Expected Annual Return", f"{exp_return:.2%}")
        c2.metric("Portfolio Risk (Std Dev)", f"{std_dev:.2%}")
        c3.metric(
            "Sharpe Ratio (Approx.)",
            f"{(exp_return - 0.04) / std_dev:.2f}",
            help="Assumes 4% risk-free rate",
        )

        st.divider()

        st.subheader("Asset Class Assumptions")
        st.write(
            "These values are loaded from `data/asset_classes/` and used for the calculations above."
        )

        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Expected Returns & Risk**")
            st.dataframe(returns_df, hide_index=True, use_container_width=True)

        with col_b:
            st.write("**Correlation Matrix**")
            st.dataframe(correlation_df, hide_index=True, use_container_width=True)

    except FileNotFoundError:
        st.error(
            "Required asset class metric files not found in `data/asset_classes/`. Please ensure `returns.csv` and `correlation.csv` exist."
        )
    except Exception as e:
        st.error(f"An error occurred while calculating metrics: {e}")
