# Portfolio Manager

A high-performance Streamlit web application designed to manage, analyze, and visualize financial holdings using **Polars**.

## Features

- **Multi-Page Dashboard**: Dedicated views for portfolio snapshots and data management.
- **Polars-Powered Engine**: Ultra-fast data processing for combining and aggregating multiple CSV files.
- **Portfolio Snapshot**:
    - Automatic loading of the latest 401K and IRA summaries.
    - Interactive breakdowns by **Account**, **Asset Class**, or **Investment**.
    - Rich visualizations using **Altair pie charts**.
    - Recursive fund expansion (splitting composite funds into underlying assets).
- **Fund Details Management**:
    - **Symbol & Asset Class Association**: Link ticker symbols and specific asset classes to fund names.
    - **Complex Compositions**: Define underlying sub-funds and weights for target-date or multi-asset funds.
    - **Data Discovery**: Automatic pre-population of symbols and fund names from your CSV data.
- **Robust Data Handling**: Diagonal concatenation to handle varying CSV schemas and currency cleaning.

## Project Structure

```text
data/
├── summaries/      # Automated tracking of current holdings (401K, IRA)
├── options/        # Institution-specific investment options
└── mappings/       # Persistent JSON mappings for symbols and classes
src/
├── app.py          # Main entry point and routing
├── data_utils.py   # Shared utilities and data discovery logic
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

### Pre-commit Hooks
Pre-commit hooks are configured to run locally via `uv`. To install them:
```bash
uv run pre-commit install
```
