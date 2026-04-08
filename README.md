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
├── summaries/      # Account-specific folders containing holdings snapshots
├── options/        # Institution-specific investment options
└── mappings/       # Unified fund_information.json mapping file
src/
├── app.py          # Main entry point and routing
├── data_utils.py   # Shared utilities and FundInfo dataclass
└── pages/          # Individual application pages
```

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
