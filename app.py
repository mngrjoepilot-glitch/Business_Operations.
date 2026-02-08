import base64
import json
from datetime import datetime

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# -----------------------------
# CONFIG (your tab naming)
# -----------------------------
TAB_RECEP = "Form Responses 1"
TAB_TECH = "Form responses 2"
TAB_WAX_HUB = "Form responses 3"

STREAMS = [
    {"label": "Recep", "tab": TAB_RECEP},
    {"label": "Tech", "tab": TAB_TECH},
    {"label": "Wax-Hub", "tab": TAB_WAX_HUB},
]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


# -----------------------------
# AUTH + SHEET
# -----------------------------
def _get_creds() -> Credentials:
    sa_b64 = st.secrets["GCP_SA_B64"]
    sa_json = base64.b64decode(sa_b64).decode("utf-8")
    sa_info = json.loads(sa_json)
    return Credentials.from_service_account_info(sa_info, scopes=SCOPES)


@st.cache_resource
def _get_sheet():
    creds = _get_creds()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["SHEET_ID"])
    return sh


# -----------------------------
# SAFE LOAD (handles duplicate headers)
# -----------------------------
def _make_unique(headers: list[str]) -> list[str]:
    seen = {}
    out = []
    for h in headers:
        h0 = (h or "").strip()
        if h0 == "":
            h0 = "Unnamed"
        if h0 not in seen:
            seen[h0] = 0
            out.append(h0)
        else:
            seen[h0] += 1
            out.append(f"{h0}__{seen[h0]}")
    return out


def load_tab(tab_name: str) -> pd.DataFrame:
    sh = _get_sheet()
    ws = sh.worksheet(tab_name)  # must match EXACTLY
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()

    headers = _make_unique(values[0])
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    # Trim whitespace in all string cells
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    return df


def standardize(df: pd.DataFrame, stream_label: str) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["Stream"] = stream_label

    # Common: Timestamp column from Google Forms is usually "Timestamp"
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    return df


def build_df_all() -> pd.DataFrame:
    parts = []
    for s in STREAMS:
        raw = load_tab(s["tab"])
        std = standardize(raw, s["label"])
        if not std.empty:
            parts.append(std)

    if not parts:
        return pd.DataFrame()

    return pd.concat(parts, ignore_index=True)


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

try:
    df_all = build_df_all()
except Exception as e:
    st.error(f"Load failed: {type(e).__name__}: {e}")
    st.stop()

c1, c2, c3 = st.columns(3)

for col, s in zip([c1, c2, c3], STREAMS):
    with col:
        st.subheader(s["label"])
        try:
            df = standardize(load_tab(s["tab"]), s["label"])
            st.write("Tab:", s["tab"])
            st.metric("Rows", len(df))
            st.metric("Cols", len(df.columns))
            st.dataframe(df.head(15), use_container_width=True)
        except Exception as e:
            st.error(f"{s['label']} failed: {type(e).__name__}: {e}")

st.divider()
st.subheader("All Streams (combined)")
st.metric("Total Rows", len(df_all))
st.metric("Total Cols", len(df_all.columns))
st.dataframe(df_all.head(50), use_container_width=True)
