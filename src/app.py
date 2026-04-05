import streamlit as st
import polars as pl
import pandas as pd

# Page Configuration
st.set_page_config(page_title="Portfolio Manager", layout="wide", page_icon="📊")

# Title and Description
st.title("📊 Portfolio Manager")
st.markdown("""
This application allows you to upload multiple CSV files, combine them using **Polars**, 
and perform various aggregations and metrics analysis.
""")

# Sidebar for file uploads
st.sidebar.header("📁 Upload Data")
truncate_ragged = st.sidebar.checkbox("Truncate ragged lines", value=True, help="Truncate rows with more fields than defined in the header.")
uploaded_files = st.sidebar.file_uploader("Choose CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        try:
            # Polars can read from a bytes IO object directly
            df = pl.read_csv(file, truncate_ragged_lines=truncate_ragged)
            dfs.append(df)
            st.sidebar.success(f"Successfully loaded: {file.name}")
        except Exception as e:
            st.sidebar.error(f"Error loading {file.name}: {e}")

    if dfs:
        try:
            # Combine dataframes using diagonal concatenation to handle differing columns gracefully
            combined_df = pl.concat(dfs, how="diagonal")
            
            st.divider()
            
            # Data Preview
            st.header("📋 Combined Data Preview")
            with st.expander("View Raw Data", expanded=True):
                st.dataframe(combined_df.to_pandas(), use_container_width=True)

            st.divider()

            # Metrics Section
            st.header("📈 Key Metrics")
            m_col1, m_col2, m_col3 = st.columns(3)
            
            m_col1.metric("Total Rows", f"{combined_df.height:,}")
            m_col2.metric("Total Columns", f"{combined_df.width:,}")
            
            # Identify numeric columns for metrics and aggregation
            numeric_cols = [
                col for col, dtype in zip(combined_df.columns, combined_df.dtypes) 
                if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]
            ]
            
            if numeric_cols:
                selected_metric_col = m_col3.selectbox("Select column for Sum metric:", numeric_cols)
                if selected_metric_col:
                    total_val = combined_df.select(pl.col(selected_metric_col).sum()).item()
                    m_col3.metric(
                        f"Sum of {selected_metric_col}", 
                        f"{total_val:,.2f}" if isinstance(total_val, float) else f"{total_val:,}"
                    )

            st.divider()

            # Summary Statistics
            st.header("📊 Summary Statistics")
            st.dataframe(combined_df.describe().to_pandas(), use_container_width=True)

            st.divider()

            # Interactive Grouping and Aggregation
            st.header("🔍 Interactive Aggregation")
            
            g_col1, g_col2, g_col3 = st.columns([2, 2, 1])
            
            group_cols = g_col1.multiselect("Group by:", combined_df.columns)
            
            if numeric_cols:
                agg_col = g_col2.selectbox("Aggregate Column:", numeric_cols)
                agg_type = g_col3.radio("Aggregation Type:", ["Sum", "Mean", "Median", "Max", "Min"])
                
                if group_cols and agg_col:
                    # Perform aggregation based on selection
                    agg_expr = None
                    if agg_type == "Sum":
                        agg_expr = pl.col(agg_col).sum()
                    elif agg_type == "Mean":
                        agg_expr = pl.col(agg_col).mean()
                    elif agg_type == "Median":
                        agg_expr = pl.col(agg_col).median()
                    elif agg_type == "Max":
                        agg_expr = pl.col(agg_col).max()
                    elif agg_type == "Min":
                        agg_expr = pl.col(agg_col).min()
                    
                    if agg_expr is not None:
                        result = combined_df.group_by(group_cols).agg(agg_expr).sort(group_cols)
                        st.subheader(f"{agg_type} of {agg_col} grouped by {', '.join(group_cols)}")
                        st.dataframe(result.to_pandas(), use_container_width=True)
                else:
                    st.info("Select one or more 'Group by' columns and an 'Aggregate Column' to see results.")
            else:
                st.warning("No numeric columns found for aggregation.")

        except Exception as e:
            st.error(f"Error processing dataframes: {e}")
            st.info("Tip: Ensure the CSV files have compatible data types if they share column names.")

else:
    # Initial state
    st.info("👈 Please upload one or more CSV files in the sidebar to begin.")
    
    # Optional: Display a small example of what the app does
    st.markdown("""
    ### Features:
    - **Fast Processing**: Uses Polars for high-performance data manipulation.
    - **Flexible Schema**: Handles CSVs with different columns using diagonal concatenation.
    - **Interactive Analysis**: Group and aggregate data on the fly.
    - **Detailed Statistics**: Instant summary stats for your entire dataset.
    """)
