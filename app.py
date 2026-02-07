import json
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

# --- Connect ---
SHEET_ID = st.secrets["sheet_id"]
sa_info = json.loads(st.secrets["gcp"]["service_account"])
creds = Credentials.from_service_account_info(
    sa_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
st.success("Connected ✅")

# --- Load tabs ---
# --- List available tabs ---
all_tabs = [ws.title for ws in sh.worksheets()]
st.write("Available tabs:", all_tabs)

# --- Use only the ones that exist ---
TABS = []
for wanted, label in [
    ("Form Responses 1", "Recep"),
    ("Form responses 2", "Tech"),
    ("Form responses 3", "Wax-Hub"),
]:
    if wanted in all_tabs:
        TABS.append((wanted, label))
    else:
        st.warning(f"Missing tab: {wanted}")

def load_tab(tab_name: str) -> pd.DataFrame:
    ws = sh.worksheet(tab_name)
    vals = ws.get_all_values()
    if len(vals) < 2:
        return pd.DataFrame()
    headers = vals[0]
    rows = vals[1:]
    df = pd.DataFrame(rows, columns=headers)
    return df

cols = st.columns(3)

for i, (tab, label) in enumerate(TABS):
    df = load_tab(tab)
    with cols[i]:
        st.subheader(label)
        st.write("Tab:", tab)
        st.metric("Rows", len(df))
        st.metric("Cols", len(df.columns))
        st.dataframe(df.head(5), use_container_width=True)


