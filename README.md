# Portfolio Manager

A Streamlit web application designed to read multiple CSV files, combine them using **Polars**, and display various aggregation metrics and data exploration tools.

## Features

- **Multiple File Upload**: Upload several CSV files at once.
- **Polars Powered**: Uses Polars for high-performance data processing.
- **Diagonal Concatenation**: Combines files even if they have slightly different column sets.
- **Summary Statistics**: Instant `describe()` results for the combined dataset.
- **Interactive Aggregation**: Group by any set of columns and perform aggregations (Sum, Mean, Median, Max, Min) on numeric columns.

## Setup and Installation

This project uses `uv` for dependency management.

### Prerequisites

- [uv](https://github.com/astral-sh/uv) installed on your system.
- Python 3.13 or higher.

### Installation

1. Clone this repository (if applicable).
2. Sync dependencies:
   ```bash
   uv sync
   ```

## Running the Application

To run the Streamlit app:

```bash
uv run streamlit run src/app.py
```

The application will be available at `http://localhost:8501`.
