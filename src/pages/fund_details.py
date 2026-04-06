import requests
import streamlit as st

from data_utils import get_all_available_funds, load_mappings, save_mappings


def scrape_vanguard_composition(url: str) -> tuple[None, str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None, f"Error: Status {response.status_code}"
        return (
            None,
            "Automatic scraping of Vanguard's complex JS site requires a headless browser. Please enter weights manually below.",
        )
    except Exception as e:
        return None, str(e)


# --- PAGE ---

_ = st.title("🏗️ Fund Details Management")
_ = st.markdown("Customize fund symbols, asset classes, and complex compositions.")

asset_map, comp_map, symbol_map = load_mappings()

# Get all unique funds {name: symbol} from existing files
available_funds_dict = get_all_available_funds()
all_known_funds = sorted(available_funds_dict.keys())

tab1, tab2 = st.tabs(["Fund Details (Symbol & Asset Class)", "Fund Compositions"])

with tab1:
    _ = st.header("General Fund Details")
    _ = st.info("Associate a symbol and an asset class with a fund name.")

    # 1. Selection
    selected_fund_name = st.selectbox(
        "Select a fund to manage:", [""] + all_known_funds
    )

    # 2. Manual entry if not selected
    manual_fund_name = st.text_input(
        "OR enter fund name manually", value=selected_fund_name
    )
    final_fund_name = manual_fund_name if manual_fund_name else selected_fund_name

    if final_fund_name:
        _ = st.divider()
        _ = st.subheader(f"Details for: {final_fund_name}")

        # Pre-populate symbol if available in files or existing mappings
        suggested_symbol = symbol_map.get(
            final_fund_name, available_funds_dict.get(final_fund_name, "")
        )

        col1, col2 = st.columns(2)

        with col1:
            current_symbol = st.text_input("Symbol / Ticker", value=suggested_symbol)

        with col2:
            asset_classes = [
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
                "Other/Cash",
            ]
            current_ac = asset_map.get(final_fund_name, "Other/Cash")
            selected_ac = st.selectbox(
                "Asset Class",
                asset_classes,
                index=asset_classes.index(current_ac)
                if current_ac in asset_classes
                else 0,
            )

        if st.button("Save Fund Details"):
            if final_fund_name:
                asset_map[final_fund_name] = selected_ac
                symbol_map[final_fund_name] = current_symbol
                save_mappings(asset_map, comp_map, symbol_map)
                _ = st.success(f"Saved details for {final_fund_name}")
                st.rerun()

    _ = st.divider()
    _ = st.subheader("Current Fund Details")

    asset_classes = [
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
        "Other/Cash",
    ]

    all_mapped_names = sorted(set(asset_map.keys()) | set(symbol_map.keys()))

    if all_mapped_names:
        # Header for the list
        h_cols = st.columns([3, 1, 2, 1])
        _ = h_cols[0].markdown("**Fund Name**")
        _ = h_cols[1].markdown("**Symbol**")
        _ = h_cols[2].markdown("**Asset Class**")
        _ = h_cols[3].markdown("**Action**")

        for name in all_mapped_names:
            cols = st.columns([3, 1, 2, 1])
            cols[0].write(name)

            # 1. Symbol Edit
            old_sym = symbol_map.get(name, "")
            new_sym = cols[1].text_input(
                f"Sym for {name}",
                value=old_sym,
                label_visibility="collapsed",
                key=f"sym_{name}",
            )

            # 2. Asset Class Edit
            old_ac = asset_map.get(name, "Other/Cash")
            new_ac = cols[2].selectbox(
                f"AC for {name}",
                asset_classes,
                index=asset_classes.index(old_ac) if old_ac in asset_classes else 0,
                label_visibility="collapsed",
                key=f"ac_{name}",
            )

            # 3. Detect changes
            if new_sym != old_sym or new_ac != old_ac:
                symbol_map[name] = new_sym
                asset_map[name] = new_ac
                save_mappings(asset_map, comp_map, symbol_map)
                st.rerun()

            # 4. Delete button
            if cols[3].button("Delete", key=f"del_{name}"):
                if name in asset_map:
                    del asset_map[name]
                if name in symbol_map:
                    del symbol_map[name]
                save_mappings(asset_map, comp_map, symbol_map)
                st.rerun()
    else:
        _ = st.write("No fund details mapped yet.")

with tab2:
    _ = st.header("Complex Fund Composition")

    # Selection list (clickable "hyperlinks")
    _ = st.subheader("All Defined Compositions")
    if comp_map:
        _ = st.info("Click a fund name to edit its composition.")
        for p in sorted(comp_map.keys()):
            if st.button(p, key=f"select_{p}"):
                st.session_state.selected_parent = p
                st.rerun()
    else:
        _ = st.write("No compositions defined yet.")

    _ = st.divider()

    # Define/Edit Section
    _ = st.subheader("Define/Edit Composition")
    _ = st.markdown("Define underlying funds and their weights (0.0 to 1.0).")

    current_selection: str = str(st.session_state.get("selected_parent", ""))  # type: ignore

    parent_fund_select = st.selectbox(
        "Select a parent fund:",
        [""] + all_known_funds,
        index=0
        if current_selection not in all_known_funds
        else (all_known_funds.index(current_selection) + 1),
        key="parent_select_box",
    )

    if parent_fund_select and parent_fund_select != current_selection:
        st.session_state.selected_parent = parent_fund_select
        current_selection = parent_fund_select

    parent_fund_manual = st.text_input(
        "OR enter parent fund name manually (Composition)",
        value=current_selection if not parent_fund_select else "",
    )
    parent_fund = parent_fund_select if parent_fund_select else parent_fund_manual

    vanguard_url = st.text_input(
        "Scrape from Vanguard URL (Optional)",
        placeholder="https://investor.vanguard.com/...",
    )
    if st.button("Try Scrape"):
        res, err = scrape_vanguard_composition(vanguard_url)
        if err:
            _ = st.warning(err)

    _ = st.divider()

    if parent_fund:
        _ = st.subheader(f"Composition for: {parent_fund}")
        current_comp = comp_map.get(parent_fund, {})

        with st.form(f"form_{parent_fund}"):
            _ = st.write("Add underlying funds (weights should sum to 1.0)")
            sub_fund_name = st.text_input("Underlying Fund Name")
            weight = st.number_input(
                "Weight (e.g. 0.355)",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                format="%.4f",
            )

            if st.form_submit_button("Add Underlying Fund"):
                current_comp[sub_fund_name] = weight
                comp_map[parent_fund] = current_comp
                save_mappings(asset_map, comp_map, symbol_map)
                _ = st.success("Added sub-fund.")

        if current_comp:
            _ = st.write("Current Composition:")
            total_w = 0
            for sf, w in list(current_comp.items()):
                total_w += w
                c = st.columns([3, 1, 1])
                c[0].write(sf)
                c[1].write(f"{w:.4f}")
                if c[2].button("Remove", key=f"rem_{parent_fund}_{sf}"):
                    del current_comp[sf]
                    comp_map[parent_fund] = current_comp
                    save_mappings(asset_map, comp_map, symbol_map)
                    st.rerun()

            _ = st.write(f"**Total Weight: {total_w:.4f}**")
            if abs(total_w - 1.0) > 0.001:
                _ = st.warning("Total weight does not sum to 1.0!")

    if st.button("Clear Selection", key="clear_comp_select"):
        st.session_state.selected_parent = ""
        st.rerun()
