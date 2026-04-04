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

The project follows a single-file application structure (`app.py`) for the frontend and business logic, leveraging Polars for "lazy" and "eager" data processing where appropriate.

## Building and Running

### Prerequisites
-   [`uv`](https://github.com/astral-sh/uv) installed.
-   Python 3.13 or higher.

### Key Commands
-   **Install Dependencies:** `uv sync`
-   **Run Application:** `uv run streamlit run app.py`
-   **Linting (Ruff):** `uv run ruff check .`
-   **Type Checking (Basedpyright):** `uv run basedpyright`
-   **Pre-commit Install:** `uv run pre-commit install`
-   **Run Pre-commit on All Files:** `uv run pre-commit run --all-files`
-   **Update Dependencies:** `uv add <package>` or `uv remove <package>`

## Development Conventions

### Coding Style
-   **Polars-First:** Always prefer Polars expressions (`pl.col(...)`) over manual Python loops or Pandas for data transformations to ensure maximum performance.
-   **Diagonal Concatenation:** When combining multiple CSVs, use `pl.concat(..., how="diagonal")` to handle varying schemas gracefully.
-   **Type Safety:** Explicitly handle numeric vs. non-numeric columns when performing aggregations.

### Project Structure
-   `app.py`: Main entry point containing the UI and data processing pipeline.
-   `pyproject.toml`: Defines project metadata and dependencies.
-   `uv.lock`: Ensures reproducible builds.
-   `.gitignore`: Standard Python template with `uv` and environment exclusions.

### Testing
-   Currently, validation is performed manually through the Streamlit interface. 
-   **TODO:** Implement automated tests for the Polars data processing logic using `pytest`.
