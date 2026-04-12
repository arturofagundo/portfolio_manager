# Gemini Context: Portfolio Manager

This project is a Streamlit-based web application designed for high-performance CSV data management and analysis using the **Polars** library.

## Project Overview

-   **Purpose:** To provide a user-friendly interface for uploading, combining, and analyzing multiple CSV files.
-   **Core Technologies:**
    -   **Streamlit:** Frontend framework for the web interface.
    -   **Polars:** Fast DataFrame library used for data manipulation and aggregation.
    -   **uv:** Modern Python package manager used for dependency management and project synchronization.
    -   **Ruff:** Fast Python linter and formatter.
    -   **Basedpyright:** Static type checker for Python.
    -   **Pre-commit:** Framework for managing and maintaining multi-language pre-commit hooks.
    -   **Pandas:** Used as a compatibility layer for Streamlit's data display components.

## Architecture

The project follows a modular multi-page Streamlit architecture. Business logic and data transformation utilities are centralized in `src/data_utils.py`, while individual views are isolated in the `src/pages/` directory.

## Building and Running

### Prerequisites
-   [`uv`](https://github.com/astral-sh/uv) installed.
-   Python 3.13 or higher.

### Key Commands
-   **Install Dependencies:** `uv sync`
-   **Run Application:** `uv run streamlit run src/app.py`
-   **Linting (Ruff):** `uv run ruff check .`
-   **Type Checking (Basedpyright):** `uv run basedpyright`
-   **Pre-commit Install:** `uv run pre-commit install`
-   **Run Pre-commit on All Files:** `uv run pre-commit run --all-files`
-   **Update Dependencies:** `uv add <package>` or `uv remove <package>`

## Development Conventions

### Coding Style
-   **Polars-First:** Always prefer Polars expressions (`pl.col(...)`) over manual Python loops or Pandas for data transformations to ensure maximum performance.
-   **Diagonal Concatenation:** When combining multiple CSVs, use `pl.concat(..., how="diagonal")` to handle varying schemas gracefully.
-   **Recursive Expansion:** Complex funds (e.g., target-date funds) should be expanded into their constituent assets using the shared expansion logic in `holdings.py`, powered by the unified `FundInfo` mapping.
-   **Multi-Account Support:** The system dynamically discovers account-specific subdirectories in `data/summaries/` and aggregates the latest data for each.

### Project Structure
-   `src/app.py`: Main router using `st.navigation`.
-   `src/data_utils.py`: Centralized Polars logic and mapping I/O; defines the `FundInfo` dataclass.
-   `src/pages/holdings.py`: Portfolio snapshot and visualization logic.
-   `src/pages/fund_details.py`: UI for managing symbols, classes, and compositions.
-   `data/summaries/`: Flattened directory structure with account-specific folders (e.g., `Google_401K/`).
-   `data/asset_classes/`: Stores asset class-specific metrics, including correlation matrices and risk/return profiles.
-   `data/mappings/fund_information.json`: Unified persistent JSON file for symbols, asset classes, and compositions.
-   `pyproject.toml`: Defines project metadata and dependencies.

### Testing
-   Automated unit tests are implemented using `pytest` for the Polars data processing logic.
-   **Run Unit Tests:** `uv run pytest --cov=src --cov-report=term-missing tests/`
