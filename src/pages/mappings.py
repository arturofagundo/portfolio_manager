import streamlit as st
import json
import os
import requests
from bs4 import BeautifulSoup
import re
from data_utils import load_mappings, save_mappings, get_all_available_funds

def scrape_vanguard_composition(url):
    """
    Attempt to scrape Vanguard fund composition.
    Note: Vanguard often uses JS to render tables, so this might need a more robust approach (Playwright) 
    or a specialized API. For now, we provide a placeholder/basic attempt.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None, f"Error: Status {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Placeholder for extraction logic - Vanguard's structure is complex
        # Often better to look for JSON data in script tags
        return None, "Automatic scraping of Vanguard's complex JS site requires a headless browser. Please enter weights manually below."
    except Exception as e:
        return None, str(e)

# --- PAGE ---

st.title("🏗️ Fund Data Management")
st.markdown("Customize how investments are classified and split into underlying assets.")

asset_map, comp_map = load_mappings()

# Get all unique funds from existing files
all_known_funds = get_all_available_funds()

tab1, tab2 = st.tabs(["Asset Class Mappings", "Fund Compositions"])

with tab1:
    st.header("Direct Asset Class Mapping")
    st.info("Map a keyword (e.g. 'Bond') to an asset class (e.g. 'Fixed Income'). Matches are case-insensitive.")
    
    # Use selectbox for better UX, but allow manual input too
    mapping_source = st.selectbox("Select a fund to map OR use manual input below", [""] + all_known_funds)
    new_asset_key = st.text_input("Investment Keyword (e.g., 'Total Stock')", value=mapping_source)
    new_asset_val = st.selectbox("Assign to Asset Class", [
        "Domestic Equities",
        "Large-Cap Equities", 
        "Mid-Cap Equities", 
        "Small-Cap Equities", 
        "Micro-Cap Equities", 
        "Value Equities", 
        "Growth Equities",
        "International Equities", 
        "Taxable Bond", 
        "Multi-Asset", 
        "Real Estate", 
        "Other/Cash"
    ])
    
    if st.button("Add/Update Mapping"):
        if new_asset_key:
            asset_map[new_asset_key] = new_asset_val
            save_mappings(asset_map, comp_map)
            st.success(f"Mapped '{new_asset_key}' to '{new_asset_val}'")

    st.divider()
    st.subheader("Current Mappings")
    
    asset_classes = [
        "Domestic Equities",
        "Large-Cap Equities", "Mid-Cap Equities", "Small-Cap Equities", 
        "Micro-Cap Equities", "Value Equities", "Growth Equities",
        "International Equities", "Taxable Bond", "Multi-Asset", 
        "Real Estate", "Other/Cash"
    ]

    if asset_map:
        for k, v in list(asset_map.items()):
            cols = st.columns([3, 2, 1])
            cols[0].write(k)
            
            # Selectbox for existing mapping
            new_v = cols[1].selectbox(
                f"Class for {k}", 
                asset_classes, 
                index=asset_classes.index(v) if v in asset_classes else 0,
                label_visibility="collapsed",
                key=f"edit_ast_{k}"
            )
            
            # If changed, update and save
            if new_v != v:
                asset_map[k] = new_v
                save_mappings(asset_map, comp_map)
                st.rerun()
                
            if cols[2].button("Delete", key=f"del_ast_{k}"):
                del asset_map[k]
                save_mappings(asset_map, comp_map)
                st.rerun()
    else:
        st.write("No mappings yet.")

with tab2:
    st.header("Complex Fund Composition")
    
    # Selection list (clickable "hyperlinks")
    st.subheader("All Defined Compositions")
    if comp_map:
        st.info("Click a fund name to edit its composition.")
        for p in sorted(comp_map.keys()):
            if st.button(p, key=f"select_{p}"):
                st.session_state.selected_parent = p
                st.rerun()
    else:
        st.write("No compositions defined yet.")
        
    st.divider()
    
    # Define/Edit Section
    st.subheader("Define/Edit Composition")
    st.markdown("Define underlying funds and their weights (0.0 to 1.0).")
    
    # Handle the selection via session state
    current_selection = st.session_state.get('selected_parent', "")
    
    parent_fund_select = st.selectbox(
        "Select a parent fund:", 
        [""] + all_known_funds,
        index=0 if not current_selection in all_known_funds else (all_known_funds.index(current_selection) + 1),
        key="parent_select_box"
    )
    
    # If the user picks something new in the selectbox, update session state
    if parent_fund_select and parent_fund_select != current_selection:
        st.session_state.selected_parent = parent_fund_select
        current_selection = parent_fund_select
        
    parent_fund_manual = st.text_input("OR enter parent fund name manually", value=current_selection if not parent_fund_select else "")
    
    parent_fund = parent_fund_select if parent_fund_select else parent_fund_manual
    
    # Scraping utility
    vanguard_url = st.text_input("Scrape from Vanguard URL (Optional)", placeholder="https://investor.vanguard.com/...")
    if st.button("Try Scrape"):
        res, err = scrape_vanguard_composition(vanguard_url)
        if err: st.warning(err)
        # Note: If successful, we would populate the fields below
    
    st.divider()
    
    if parent_fund:
        st.subheader(f"Composition for: {parent_fund}")
        current_comp = comp_map.get(parent_fund, {})
        
        # UI for adding underlying funds
        with st.form(f"form_{parent_fund}"):
            st.write("Add underlying funds (weights should sum to 1.0)")
            
            sub_fund_name = st.text_input("Underlying Fund Name")
            weight = st.number_input("Weight (e.g. 0.355)", min_value=0.0, max_value=1.0, step=0.001, format="%.4f")
            
            if st.form_submit_button("Add Underlying Fund"):
                current_comp[sub_fund_name] = weight
                comp_map[parent_fund] = current_comp
                save_mappings(asset_map, comp_map)
                st.success("Added sub-fund.")

        # Show and manage current composition
        if current_comp:
            st.write("Current Composition:")
            total_w = 0
            for sf, w in list(current_comp.items()):
                total_w += w
                c = st.columns([3, 1, 1])
                c[0].write(sf)
                c[1].write(f"{w:.4f}")
                if c[2].button("Remove", key=f"rem_{parent_fund}_{sf}"):
                    del current_comp[sf]
                    comp_map[parent_fund] = current_comp
                    save_mappings(asset_map, comp_map)
                    st.rerun()
            
            st.write(f"**Total Weight: {total_w:.4f}**")
            if abs(total_w - 1.0) > 0.001:
                st.warning("Total weight does not sum to 1.0!")
                
    if st.button("Clear Selection"):
        st.session_state.selected_parent = ""
        st.rerun()
