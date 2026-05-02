import os
from datetime import date

import pandas as pd
import polars as pl
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from data_utils import (
    FundInfo,
    get_all_account_names,
    get_latest_file,
    load_fund_info,
    save_fund_info,
    validate_summary_csv,
)


def save_uploaded_file(uploaded_file: UploadedFile, target_path: str) -> None:
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(uploaded_file.getbuffer())


# --- PAGE CONFIG ---
st.title("🗂️ Data Management Workflow")
st.markdown(
    "Easily manage your portfolio data structure, from adding new accounts to fine-tuning individual holdings."
)

# --- NAVIGATION STATE ---
if "dm_active_tab" not in st.session_state:
    st.session_state.dm_active_tab = "🆕 Add New Account"

# Segmented control for tabs
active_tab = st.radio(
    "Navigation",
    [
        "🆕 Add New Account",
        "🔄 Update Investment Options",
        "📄 Update Individual Holdings",
    ],
    index=[
        "🆕 Add New Account",
        "🔄 Update Investment Options",
        "📄 Update Individual Holdings",
    ].index(st.session_state.dm_active_tab),
    horizontal=True,
    label_visibility="collapsed",
)
st.session_state.dm_active_tab = active_tab

st.write("---")

# Shared data
fund_info = load_fund_info()
existing_accounts = get_all_account_names()

if active_tab == "🆕 Add New Account":
    st.header("Add a New Account")

    st.markdown("#### Step 1: Account Identity")
    c1, c2 = st.columns(2)
    new_acc_type = c1.selectbox("Account Type", ["401K", "IRA"], key="add_type")
    new_acc_name = c2.text_input(
        "Institution Name", placeholder="e.g. Google, Amazon, Fidelity"
    )

    if new_acc_name:
        clean_name = new_acc_name.strip().replace(" ", "_")
        summary_folder = f"{clean_name}_{new_acc_type}"
        summary_dir = os.path.join("data", "summaries", summary_folder)

        st.markdown("#### Step 2: Provide Holdings Data")
        upload_choice = st.radio(
            "How would you like to provide initial data?",
            ["Upload CSV", "Start with Empty Template"],
            horizontal=True,
        )

        df_to_save: pd.DataFrame | None = None

        if upload_choice == "Upload CSV":
            summary_file_obj = st.file_uploader(
                "Upload provider export (CSV)", type="csv"
            )
            if summary_file_obj:
                try:
                    df_temp = pd.read_csv(summary_file_obj)
                    st.success("File uploaded successfully!")
                    with st.expander("🔍 Preview Uploaded Data"):
                        st.dataframe(df_temp.head(10))

                    is_valid, err_msg = validate_summary_csv(
                        pl.from_pandas(df_temp), str(new_acc_type)
                    )
                    if is_valid:
                        df_to_save = df_temp
                    else:
                        st.error(err_msg)
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")
        else:
            st.info("Creating an empty template for you to fill in the next tab.")
            if new_acc_type == "401K":
                df_to_save = pd.DataFrame(
                    columns=["Fund name", "Quantity", "Price", "Current balance"]
                )
            else:
                df_to_save = pd.DataFrame(
                    columns=["Description", "Quantity", "Symbol", "Current Value"]
                )

        st.markdown("#### Step 3: Investment Options (Optional)")
        st.caption("List of all funds available in this account.")
        options_file_obj = st.file_uploader(
            "Upload options.csv", type="csv", key="new_acc_options"
        )

        if st.button("🚀 Create Account", use_container_width=True):
            if df_to_save is not None:
                os.makedirs(summary_dir, exist_ok=True)
                today = date.today().strftime("%Y-%m-%d")
                summary_path = os.path.join(summary_dir, f"{today}_{clean_name}.csv")
                df_to_save.to_csv(summary_path, index=False)

                if options_file_obj:
                    options_path = os.path.join(
                        "data", "options", str(new_acc_type), clean_name, "options.csv"
                    )
                    save_uploaded_file(options_file_obj, options_path)

                st.success(f"Successfully created {new_acc_name} {new_acc_type}!")

                # Redirect to Update Individual Holdings if template was used
                if upload_choice == "Start with Empty Template":
                    st.session_state.dm_active_tab = "📄 Update Individual Holdings"
                    st.session_state.selected_edit_acc = (
                        f"{new_acc_name.strip()} {new_acc_type}"
                    )

                st.balloons()
                st.rerun()
            else:
                st.error("Please provide holdings data via upload or template.")

elif active_tab == "🔄 Update Investment Options":
    st.header("Update Investment Options")
    st.info("Update the list of available funds for an existing account.")

    if not existing_accounts:
        st.warning("No existing accounts found. Add an account first.")
    else:
        selected_acc = st.selectbox(
            "Select Account", existing_accounts, key="opt_acc_select"
        )

        if selected_acc:
            # Parse Type and Name
            if " " in selected_acc:
                parts = selected_acc.rsplit(" ", 1)
                acc_name_only = parts[0].replace(" ", "_")
                acc_type_only = parts[1]
            else:
                acc_name_only = selected_acc
                acc_type_only = "401K"

            options_dir = os.path.join("data", "options", acc_type_only, acc_name_only)
            options_path = os.path.join(options_dir, "options.csv")

            if os.path.exists(options_path):
                st.markdown("#### Current Options")
                options_df = pd.read_csv(options_path)
                st.dataframe(options_df, hide_index=True, use_container_width=True)
            else:
                st.info(f"No options file found at `{options_path}`.")

            st.write("---")
            st.markdown("#### ➕ Add New Option Manually")
            with st.form("add_manual_option"):
                m_col1, m_col2, m_col3 = st.columns(3)
                new_fund = m_col1.text_input("Fund Name")
                new_sym = m_col2.text_input("Symbol (Optional)")

                asset_classes = [
                    "Domestic Equities",
                    "International Equities",
                    "Mid-Cap",
                    "Small-Cap",
                    "Micro-Cap",
                    "Real Estate",
                    "Bonds",
                    "Other/Cash",
                ]
                new_ac = m_col3.selectbox(
                    "Asset Class (Optional)", [""] + asset_classes
                )

                if st.form_submit_button("Add to Options & Mapping"):
                    if not new_fund:
                        st.error("Fund Name is required.")
                    else:
                        new_row = {
                            "Fund name": new_fund,
                            "Symbol": new_sym,
                            "Expense ratio": "",
                            "Risk potential": "",
                        }
                        if os.path.exists(options_path):
                            existing_df = pd.read_csv(options_path)
                            updated_df = pd.concat(
                                [existing_df, pd.DataFrame([new_row])],
                                ignore_index=True,
                            )
                        else:
                            updated_df = pd.DataFrame([new_row])

                        os.makedirs(options_dir, exist_ok=True)
                        updated_df.to_csv(options_path, index=False)

                        if new_ac:
                            if new_fund not in fund_info:
                                fund_info[new_fund] = FundInfo()
                            fund_info[new_fund].asset_class = new_ac
                            fund_info[new_fund].symbol = new_sym
                            save_fund_info(fund_info)

                        st.success(f"Added '{new_fund}'.")
                        st.rerun()

            st.write("---")
            st.markdown("#### ⬆️ Bulk Upload Options File")
            new_options_file_obj = st.file_uploader(
                "Choose options.csv", type="csv", key="update_options"
            )
            if st.button("Overwrite Options"):
                if new_options_file_obj:
                    save_uploaded_file(new_options_file_obj, options_path)
                    st.success("Updated options.")
                    st.rerun()

elif active_tab == "📄 Update Individual Holdings":
    st.header("Update Individual Holdings")
    st.markdown("Manually edit, add, or remove holdings for a specific account.")

    if not existing_accounts:
        st.warning("No existing accounts found.")
    else:
        # Check if we have a manually tracked selection
        if "selected_edit_acc" not in st.session_state:
            st.session_state.selected_edit_acc = existing_accounts[0]

        # Use index to control selection without key collision
        default_index = 0
        if st.session_state.selected_edit_acc in existing_accounts:
            default_index = existing_accounts.index(st.session_state.selected_edit_acc)

        edit_acc = st.selectbox(
            "Select Account to Edit", existing_accounts, index=default_index
        )
        # Update our manual state whenever the user interacts with the selectbox
        st.session_state.selected_edit_acc = edit_acc

        if edit_acc:
            # Find the latest file
            folder_name = edit_acc.replace(" ", "_")
            acc_dir = os.path.join("data", "summaries", folder_name)
            latest_file = get_latest_file(acc_dir)

            if not latest_file:
                st.error(f"No summary files found in {acc_dir}")
            else:
                st.caption(f"Editing latest file: `{os.path.basename(latest_file)}`")
                df_to_edit = pd.read_csv(latest_file)

                # Hide specific columns from display if they exist
                column_config = {}
                if "Contributions mix" in df_to_edit.columns:
                    column_config["Contributions mix"] = None

                edited_df = st.data_editor(
                    df_to_edit,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="holdings_editor",
                    column_config=column_config,
                )

                col_s1, col_s2 = st.columns([1, 3])
                save_mode = col_s1.radio(
                    "Save Mode", ["Update Latest", "Create New (Today)"]
                )

                if col_s2.button("💾 Save Changes", use_container_width=True):
                    target_file = latest_file
                    if save_mode == "Create New (Today)":
                        today_str = date.today().strftime("%Y-%m-%d")
                        base_name = folder_name.rsplit("_", 1)[0]
                        target_file = os.path.join(
                            acc_dir, f"{today_str}_{base_name}.csv"
                        )

                    edited_df.to_csv(target_file, index=False)
                    st.success(f"Saved changes to {os.path.basename(target_file)}")
                    st.balloons()

            st.write("---")
            with st.expander("🛠️ Advanced: Rename Account"):
                st.warning(
                    "Renaming will update all history files and investment option folders."
                )
                new_name_input = st.text_input(
                    "New Account Name", placeholder="e.g. Google New"
                )
                if st.button("Confirm Rename"):
                    if new_name_input:
                        try:
                            # 1. Parse current info
                            # folder_name is e.g. "Amazon_401K"
                            old_clean_name, acc_type = folder_name.rsplit("_", 1)
                            new_clean_name = new_name_input.strip().replace(" ", "_")
                            new_folder_name = f"{new_clean_name}_{acc_type}"

                            # 2. Rename Summary Directory
                            new_acc_dir = os.path.join(
                                "data", "summaries", new_folder_name
                            )
                            if os.path.exists(new_acc_dir):
                                st.error(f"Account {new_name_input} already exists!")
                            else:
                                # Rename summary folder
                                os.rename(acc_dir, new_acc_dir)

                                # Rename all files inside summary folder to match new name
                                for f in os.listdir(new_acc_dir):
                                    if f.endswith(".csv") and old_clean_name in f:
                                        old_f_path = os.path.join(new_acc_dir, f)
                                        new_f_path = os.path.join(
                                            new_acc_dir,
                                            f.replace(old_clean_name, new_clean_name),
                                        )
                                        os.rename(old_f_path, new_f_path)

                                # 3. Rename Options Directory
                                old_options_dir = os.path.join(
                                    "data", "options", acc_type, old_clean_name
                                )
                                new_options_dir = os.path.join(
                                    "data", "options", acc_type, new_clean_name
                                )
                                if os.path.exists(old_options_dir):
                                    os.rename(old_options_dir, new_options_dir)

                                st.success(f"Renamed to {new_name_input}")
                                # Safely update the manual tracking variable
                                st.session_state.selected_edit_acc = (
                                    f"{new_name_input.strip()} {acc_type}"
                                )
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error renaming: {e}")
                    else:
                        st.error("Please enter a new name.")

st.divider()
with st.expander("ℹ️ About the Data Structure"):
    st.markdown("""
    - **Summaries:** `data/summaries/<AccountName>_<Type>/YYYY-MM-DD_<AccountName>.csv`
    - **Options:** `data/options/<Type>/<AccountName>/options.csv`
    """)
