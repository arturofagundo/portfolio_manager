import streamlit as st

# Page Configuration
st.set_page_config(page_title="Portfolio Manager", layout="wide", page_icon="💰")

# --- ROUTING ---

pg = st.navigation(
    {
        "Main": [
            st.Page("pages/holdings.py", title="Portfolio Holdings", icon="💰"),
            st.Page(
                "pages/allocation_sandbox.py", title="Allocation Sandbox", icon="🏖️"
            ),
            st.Page("pages/project_growth.py", title="Projected Growth", icon="🚀"),
        ],
        "Analysis & Setup": [
            st.Page("pages/data_management.py", title="Data Management", icon="🗂️"),
            st.Page("pages/fund_details.py", title="Fund Details Management", icon="🏗️"),
            st.Page(
                "pages/portfolio_metrics.py", title="Performance Metrics", icon="📈"
            ),
        ],
    }
)
pg.run()
