# Gemini Context: Portfolio Manager

This project is a Streamlit-based web application designed for high-performance CSV data management and analysis using the **Polars** library.

## Project Overview

-   **Purpose:** To provide a user-friendly interface for managing, analyzing, and projecting financial holdings.
-   **Core Technologies:**
    -   **Streamlit:** Frontend framework for the web interface.
    -   **Polars:** High-performance DataFrame library for core data manipulation.
    -   **cvxpy & PyPortfolioOpt:** Optimization engines for Mean-Variance Optimization (MVO).
    -   **uv:** Modern Python package manager for dependency and project synchronization.
    -   **Altair:** Declarative visualization library for charts and simulations.

## Architecture

The project follows a modular multi-page Streamlit architecture. Business logic is centralized in `src/data_utils.py`, while feature-specific logic is isolated in the `src/pages/` directory.

### Key Pages
-   **Portfolio Snapshot (`holdings.py`):** Interactive overview of current holdings with account-level drill-downs and composite fund identification (italics).
-   **Projected Growth (`project_growth.py`):** Monte-Carlo simulation (500 paths) with MVO, quarterly rebalancing, and inflation-adjusted contributions.
-   **Allocation Sandbox (`allocation_sandbox.py`):** MVO-based rebalancing tool with account-level constraints and running balance transaction logs.

## Building and Running

### Prerequisites
-   [`uv`](https://github.com/astral-sh/uv) installed.
-   Python 3.13 or higher.

### Key Commands
-   **Install Dependencies:** `uv sync`
-   **Run Application:** `uv run streamlit run src/app.py`
-   **Linting (Ruff):** `uv run ruff check .`
-   **Type Checking (Basedpyright):** `uv run basedpyright`

## Development Conventions

### Coding Style
-   **Optimization-First:** Use `cvxpy` for rebalancing and allocation logic. Support both unconstrained and account-constrained (menu-restricted) modes.
-   **Probabilistic Projection:** Monte-Carlo simulations should use multivariate normal distributions based on the historical metrics in `data/asset_classes/`.
-   **Recursive Expansion:** Composite funds (e.g., Target Date funds) are expanded into underlying assets using `data_utils.expand_holdings`.
-   **Italicized Composites:** In UI tables, composite funds are identified with italics in the Asset Class column for clarity.

### Data Privacy & Security
-   **Selective Tracking:** The `.gitignore` uses a `data/*` + `!subdirectory/` pattern to allow tracking of non-sensitive metrics (`asset_classes`, `mappings`) while strictly ignoring personal balances (`summaries`, `options`).
-   **Asset Metrics:** Historical nominal returns (1996–2025) are the default for all projections.

### Project Structure
-   `src/app.py`: Main router with logical grouping (Main vs. Analysis & Setup).
-   `data/asset_classes/`: Stores `returns.csv` (Expected Return/Std Dev) and `correlation.csv`.
-   `data/mappings/fund_information.json`: Local mapping for symbols, asset classes, and compositions.

### Testing
-   **Run Unit Tests:** `uv run pytest --cov=src --cov-report=term-missing tests/`
