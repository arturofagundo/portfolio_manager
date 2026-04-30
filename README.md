# Portfolio Manager

A high-performance Streamlit web application designed to manage, analyze, and visualize financial holdings using **Polars**.

## Features

- **Multi-Page Dashboard**: Dedicated views for portfolio snapshots and data management.
- **Polars-Powered Engine**: Ultra-fast data processing for combining and aggregating multiple CSV files.
- **Portfolio Snapshot**:
    - **Dynamic Account Discovery**: Automatically loads and aggregates data from account-specific directories (e.g., `Google_401K`, `Jump_401K`).
    - **Latest Status**: Displays update dates for both 401K and IRA accounts.
    - Interactive breakdowns by **Account**, **Asset Class**, or **Investment**.
    - Rich visualizations using **Altair pie charts**.
    - Recursive fund expansion (splitting composite funds into underlying assets).
- **Fund Details Management**:
    - **Unified Fund Metadata**: Single point of truth for fund symbols, asset classes, and compositions via `fund_information.json`.
    - **Complex Compositions**: Define underlying sub-funds and weights for target-date or multi-asset funds.
    - **Data Discovery**: Automatic pre-population of symbols and fund names from your CSV data.

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

**Current Methodology:** Historical Nominal Returns (30-year horizon, approx. 1996–2025).

**Sources:**
- **Domestic Equities (S&P 500):** Fidelity / S&P Global.
- **International Equities (MSCI ACWI ex-US):** MSCI / Thoughtful Finance.
- **Mid-Cap (S&P MidCap 400) & Small-Cap (S&P SmallCap 600):** S&P Global / YCharts.
- **Micro-Cap (CRSP 9-10 / DFSCX):** Dimensional Fund Advisors / Center for Research in Security Prices.
- **Real Estate (FTSE NAREIT All Equity):** Nareit / FTSE Russell.
- **Bonds (Bloomberg US Aggregate):** Bloomberg / Investing.com.

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
