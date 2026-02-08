import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# ======================
# AUTH
# ======================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds = Credentials.from_service_account_info(
    st.secrets["gcp"]["service_account"],
    scopes=SCOPES
)

gc = gspread.authorize(creds)

SHEET_ID = st.secrets["SHEET_ID"]
sh = gc.open_by_key(SHEET_ID)


# ======================
# TAB NAMES (MUST MATCH GOOGLE SHEET)
# ======================
TAB_RECEP   = "Recep"
TAB_TECH    = "Tech"
TAB_WAX_HUB = "Wax-Hub"


# ======================
# LOAD
# ======================
def load_tab(tab_name: str) -> pd.DataFrame:
    ws = sh.worksheet(tab_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)


# ======================
# DISPLAY
# ======================
def show_tab(col, label: str, tab_name: str):
    with col:
        st.subheader(label)
        try:
            df = load_tab(tab_name)
            st.metric("Rows", len(df))
            st.metric("Cols", len(df.columns))
            st.dataframe(df.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"{label} failed: {e}")


# ======================
# UI
# ======================
c1, c2, c3 = st.columns(3)

show_tab(c1, "Recep", "Recep")
show_tab(c2, "Tech", "Tech")
show_tab(c3, "Wax-Hub", "Wax-Hub")
