# app.py
import base64
import json

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
TAB_RECEP = "Recep"
TAB_TECH = "Tech"
TAB_WAX_HUB = "Wax-Hub"


# ====== CONFIG (LOCKED) ======
TAB_RECEP = "Form Responses 1"
TAB_TECH = "Form responses 2"
TAB_WAX_HUB = "Form responses 3"



# ====== AUTH (LOCKED) ======
SHEET_ID = st.secrets["SHEET_ID"]
sa_info = json.loads(base64.b64decode(st.secrets["GCP_SA_B64"]).decode("utf-8"))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)

gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)


# ====== LOAD (LOCKED) ======
def load_tab(tab_name: str) -> pd.DataFrame:
    ws = sh.worksheet(tab_name)
    data = ws.get_all_records()  # expects header row
    return pd.DataFrame(data)


def show_tab(col, label: str, tab_name: str):
    with col:
        st.subheader(label)
        try:
            try:
    df = load_tab(tab_name)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    start, end = st.date_input(
        "Date range",
        [df["Timestamp"].min().date(), df["Timestamp"].max().date()]
    )

    df = df[
        (df["Timestamp"].dt.date >= start) &
        (df["Timestamp"].dt.date <= end)
    ]

    st.write("Tab:", tab_name)
    st.metric("Rows", len(df))
    st.metric("Cols", len(df.columns))
    st.dataframe(df.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"{label} failed: {type(e).__name__}: {e}")


# ====== UI (LOCKED) ======
st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

c1, c2, c3 = st.columns(3)
show_tab(c1, "Recep", TAB_RECEP)
show_tab(c2, "Tech", TAB_TECH)
show_tab(c3, "Wax-Hub", TAB_WAX_HUB)
