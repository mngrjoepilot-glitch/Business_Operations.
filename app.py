# app.py  (FULL, LOCKED VERSION)

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# -------------------
# CONFIG (LOCKED)
# -------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

TAB_RECEP   = "Form Responses 1"
TAB_TECH    = "Form responses 2"
TAB_WAX_HUB = "Form responses 3"

st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

# -------------------
# AUTH (LOCKED)
# Secrets MUST contain:
# SHEET_ID = "..."
# [gcp] with service account fields
# -------------------
SHEET_ID = st.secrets["SHEET_ID"]
sa_info = dict(st.secrets["gcp"])

creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

st.success(f"Connected ✅  ({sh.title})")

# -------------------
# LOAD (LOCKED)
# -------------------
def load_tab(tab_name: str) -> pd.DataFrame:
    ws = sh.worksheet(tab_name)           # fails if tab name mismatch
    data = ws.get_all_records()           # expects header row in the Form sheet (it has)
    return pd.DataFrame(data)

def show_tab(col, label: str, tab_name: str):
    with col:
        st.subheader(label)
        try:
            df = load_tab(tab_name)
            st.write("Tab:", tab_name)
            st.metric("Rows", len(df))
            st.metric("Cols", len(df.columns))
            st.dataframe(df.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"{label} failed: {type(e).__name__}: {e}")

c1, c2, c3 = st.columns(3)

show_tab(c1, "Recep", TAB_RECEP)
show_tab(c2, "Tech", TAB_TECH)
show_tab(c3, "Wax-Hub", TAB_WAX_HUB)
