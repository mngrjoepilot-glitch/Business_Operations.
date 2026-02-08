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

# ===== Step 1: Data Contract (LOCKED) =====
CONTRACT = {
    "Recep": {
        "tab": "Form Responses 1",
        "timestamp": "Timestamp",
        "client_name": "Name of client",
        "phone": "Client Phone number",
        "service": "Service provided",
        "provider": "Service provider's Name",
        "payment_mode": "Mode of Payment",
        "service_cost": "Service Cost",
        "technician_payout": "Technician Payout",
    },
    "Tech": {
        "tab": "Form responses 2",
        "timestamp": "Timestamp",
        "provider": "Service provider's Name",
        "service": "Service provided",
        "payment_mode": "Mode of Payment",
        "service_cost": "Service Cost",
        "technician_payout": "Technician Payout",
    },
    "Wax-Hub": {
        "tab": "Form responses 3",
        "timestamp": "Timestamp",
        "client_name": "Name of client",
        "phone": "Client Phone number",
        "service": "Service provided",
        "provider": "Service provider's Name",
        "payment_mode": "Mode of Payment",
        "service_cost": "Service Cost",
        "technician_payout": "Technician Payout",
    },
}



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

    # pull raw grid (no header assumptions)
    values = ws.get_all_values()

    # find first non-empty row to use as header
    header_idx = None
    for i, row in enumerate(values):
        if any(str(c).strip() for c in row):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()

    headers = [str(h).strip() if str(h).strip() else f"col_{j}" for j, h in enumerate(values[header_idx])]

    # make headers unique (handles duplicates safely)
    seen = {}
    clean = []
    for h in headers:
        k = seen.get(h, 0)
        clean.append(h if k == 0 else f"{h}_{k}")
        seen[h] = k + 1

    data = values[header_idx + 1 :]
    df = pd.DataFrame(data, columns=clean)

    # drop fully empty rows
    df = df.replace(r"^\s*$", pd.NA, regex=True).dropna(how="all")
    return df



def show_tab(col, label: str, tab_name: str):
    with col:
        st.subheader(label)
        try:
            df = load_tab(tab_name)

            df["Timestamp"] = pd.to_datetime(
                df["Timestamp"], errors="coerce"
            )

            start, end = st.date_input(
                "Date range",
                [
                    df["Timestamp"].min().date(),
                    df["Timestamp"].max().date(),
                ],
            )

            df = df[
                (df["Timestamp"].dt.date >= start)
                & (df["Timestamp"].dt.date <= end)
            ]

            st.write("Tab:", tab_name)
            st.metric("Rows", len(df))
            st.metric("Cols", len(df.columns))
            st.dataframe(df.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"Failed ({tab_name}): {type(e).__name__}: {e}")


# ====== UI (LOCKED) ======
st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

c1, c2, c3 = st.columns(3)
show_tab(c1, "Recep", TAB_RECEP)
show_tab(c2, "Tech", TAB_TECH)
show_tab(c3, "Wax-Hub", TAB_WAX_HUB)
