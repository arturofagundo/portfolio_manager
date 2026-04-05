import streamlit as st
import polars as pl
import pandas as pd
import os
import json
from data_utils import load_mappings, save_mappings

# Page Configuration
st.set_page_config(page_title="Portfolio Manager", layout="wide", page_icon="💰")

# --- ROUTING ---

pg = st.navigation([
    st.Page("pages/holdings.py", title="Portfolio Holdings", icon="💰"),
    st.Page("pages/mappings.py", title="Fund Data Management", icon="🏗️"),
])
pg.run()
