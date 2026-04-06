import streamlit as st

# Page Configuration
st.set_page_config(page_title="Portfolio Manager", layout="wide", page_icon="💰")

# --- ROUTING ---

pg = st.navigation(
    [
        st.Page("pages/holdings.py", title="Portfolio Holdings", icon="💰"),
        st.Page("pages/fund_details.py", title="Fund Details Management", icon="🏗️"),
    ]
)
pg.run()
