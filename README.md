# Portfolio Manager

A high-performance Streamlit web application designed to manage, analyze, and visualize financial holdings using **Polars**.

## Features

- **Multi-Page Dashboard**: Dedicated views for portfolio snapshots, metrics, and simulations.
- **Projected Growth Simulation**: Monte-Carlo simulation (500 paths) with quarterly rebalancing, inflation-adjusted contributions, and Mean-Variance Optimization (MVO).
- **Allocation Sandbox**: Advanced asset allocation tool with account-level constraints and rebalancing transaction recommendations.
- **Portfolio Snapshot**:
    - **Dynamic Account Discovery**: Automatically loads and aggregates data from account-specific directories.
    - **Interactive Summary**: Drill-down into specific accounts to see detailed holdings and asset classes.
    - Recursive fund expansion (splitting composite funds into underlying assets).
- **Fund Details Management**:
    - **Unified Fund Metadata**: Single point of truth for fund symbols, asset classes, and compositions via `fund_information.json`.
    - **Complex Compositions**: Define underlying sub-funds and weights for target-date or multi-asset funds.

## Project Structure

```text
data/
├── summaries/      # Account-specific folders (e.g., Google_401K, Jump_401K)
├── options/        # Institution-specific investment options (e.g., Google, Jump)
├── asset_classes/  # Asset class metrics (correlation, risk, return)
└── mappings/       # Unified fund_information.json mapping file
src/
├── app.py          # Main entry point and routing
├── data_utils.py   # Shared utilities and FundInfo dataclass
└── pages/          # Individual application pages
```

## Data Schema

Since the `data/` directory is excluded from version control for privacy, you must recreate the following structure for the application to function. **Sample files for each type are provided in `data/samples/` as a reference.**

### 1. Account Summaries (`data/summaries/`)
The app expects subdirectories for each account. The folder name identifies the account.
- **401K Accounts**: Files should contain `YYYY-MM-DD` in the filename and use these columns:
    - `Fund name`: Name of the investment.
    - `Quantity`: Number of shares held.
    - `Current balance`: Total value (currency string, e.g., "$1,234.56").
- **IRA Accounts**: Files should contain `IRA` in the parent folder name and use these columns:
    - `Description`: Name of the investment.
    - `Account Name`: Specific sub-account name.
    - `Quantity`: Number of shares held.
    - `Current Value`: Total value (currency string).

### 2. Investment Options (`data/options/`)
Subdirectories containing `options.csv` files used for data discovery:
- `Fund name`: Official name of the fund.
- `Symbol`: Ticker symbol (optional).

### 3. Fund Mappings (`data/mappings/fund_information.json`)
A JSON file mapping fund names to metadata and compositions:
```json
{
  "Fund Name": {
    "Symbol": "TICKER",
    "Asset Class": "Asset Category",
    "Composition": {
      "Underlying Fund A": 0.6,
      "Underlying Fund B": 0.4
    }
  }
}
```

## Asset Class Metrics

The application uses historical nominal returns and standard deviations for portfolio analysis, located in `data/asset_classes/returns.csv`.

**Current Methodology:** 30-Year Historical Performance (Approx. 1995–2025).

| Asset Class | Annualized Return | Standard Deviation | Risk-Adjusted (Sharpe) |
| :--- | :--- | :--- | :--- |
| **Large-Cap (Domestic Equities)** | 10.5% | 15.2% | 0.49 |
| **Mid-Cap** | 11.2% | 17.8% | 0.52 |
| **Small-Cap** | 9.8% | 19.6% | 0.38 |
| **Micro-Cap** | 9.2% | 23.1% | 0.31 |
| **Int'l Developed (International)** | 5.9% | 17.2% | 0.21 |
| **Fixed Income (Bonds)** | 4.3% | 4.9% | 0.42 |
| **REITs (Real Estate)** | 9.4% | 19.1% | 0.36 |

**Sources:** The historical return and standard deviation data is aggregated from several long-term financial benchmarks and institutional reports. For the 30-year window (1995–2025), the data is primarily derived from the following index providers and market researchers:

**Core Index Benchmarks**
- **Large-Cap**: S&P 500 (Standard & Poor's) – The widely accepted benchmark for domestic large-cap equities.
- **Mid-Cap**: S&P MidCap 400 – Used to track the "mid-cap anomaly" that has seen this segment outperform both large and small caps over several decades.
- **Small-Cap**: Russell 2000 (FTSE Russell) – The standard benchmark for the small-cap market, frequently compared against large-caps for "size premium" analysis.
- **Micro-Cap**: Russell Microcap – Provides the longest reliable data set for the smallest publicly traded companies.
- **International**: MSCI EAFE Index – The industry standard for developed markets outside North America.
- **Real Estate**: FTSE Nareit All Equity REITs – The primary index used to track the historical performance of publicly traded real estate investment trusts.
- **Bonds**: Bloomberg US Aggregate Bond Index – The foundational index for the total U.S. bond market.

**Historical Context:**
- **Mid-Cap Premium:** Established mid-cap companies have historically outperformed both large and small caps, balancing growth potential with stability.
- **Small-Cap Lag:** Small-caps have underperformed Large-caps over this specific 30-year window, highlighting periods where mega-cap dominance persists.
- **Micro-Cap Volatility:** Highest risk (23.1%) but lower returns in this window, reflecting a "lottery ticket" profile where major winners are offset by higher failure rates.
- **International Lag:** Developed international markets (MSCI EAFE) have significantly trailed U.S. markets over this specific multi-decade cycle.

## Setup and Installation

This project uses [uv](https://github.com/astral-sh/uv) for modern Python dependency management.

### Prerequisites

- `uv` installed on your system.
- Python 3.13 or higher.

### Installation

1. Clone this repository.
2. Sync dependencies and create a virtual environment:
   ```bash
   uv sync
   ```

## Running the Application

To launch the Streamlit app:

```bash
uv run streamlit run src/app.py
```

The application will be available at `http://localhost:8501`.

## Development

### Linting and Type Checking
The project uses **Ruff** for linting/formatting and **Basedpyright** for static type checking.

- **Run Linting:** `uv run ruff check .`
- **Run Type Checker:** `uv run basedpyright`
- **Run Unit Tests:** `uv run pytest --cov=src --cov-report=term-missing tests/`

### Pre-commit Hooks
Pre-commit hooks are configured to run locally via `uv`. To install them:
```bash
uv run pre-commit install
```
 run basedpyright`
- **Run Unit Tests:** `uv run pytest --cov=src --cov-report=term-missing tests/`

### Pre-commit Hooks
Pre-commit hooks are configured to run locally via `uv`. To install them:
```bash
uv run pre-commit install
```
