import base64
import json
from datetime import date

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# =========================
# CONFIG (tabs you settled)
# =========================
TAB_RECEP = "Form Responses 1"
TAB_TECH = "Form responses 2"
TAB_WAX_HUB = "Form responses 3"

STREAM_TABS = [
    {"label": "Recep", "tab": TAB_RECEP, "stream": "Recep"},
    {"label": "Tech", "tab": TAB_TECH, "stream": "Tech"},
    {"label": "Wax-Hub", "tab": TAB_WAX_HUB, "stream": "Wax-Hub"},
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


# =========================
# AUTH (Streamlit secrets)
# Secrets required:
#   SHEET_ID = "..."
#   GCP_SA_B64 = "base64(service_account.json)"
# =========================
def get_gspread_client():
    SHEET_ID = st.secrets["SHEET_ID"]
    sa_b64 = st.secrets["GCP_SA_B64"]

    sa_json_str = base64.b64decode(sa_b64).decode("utf-8")
    sa_info = json.loads(sa_json_str)

    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc, SHEET_ID


# =========================
# SHEET → DF (handles duplicate headers)
# =========================
def make_unique_headers(headers):
    seen = {}
    out = []
    for h in headers:
        h = (h or "").strip()
        if h == "":
            h = "Unnamed"
        if h not in seen:
            seen[h] = 0
            out.append(h)
        else:
            seen[h] += 1
            out.append(f"{h}__{seen[h]}")
    return out


def load_tab_df(sh, tab_name: str) -> pd.DataFrame:
    ws = sh.worksheet(tab_name)
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()

    headers = make_unique_headers(values[0])
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    # drop fully-empty rows
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    return df


# =========================
# STANDARDIZE + VALIDATE
# =========================
COLUMN_MAP = {
    "Timestamp": "Timestamp",
    "timestamp": "Timestamp",

    "Service Provided": "Service",
    "service provided": "Service",
    "Service": "Service",

    "Price": "Price",
    "price": "Price",
    "Amount": "Price",
    "amount": "Price",
}

REQUIRED = ["Stream", "Timestamp", "Service", "Price"]


def standardize_df(df: pd.DataFrame, stream_name: str) -> pd.DataFrame:
    if df.empty:
        return df

    # Stream column (mandatory)
    df["Stream"] = stream_name

    # rename columns using map (case-sensitive map + fallback strip)
    df = df.rename(columns={c: c.strip() for c in df.columns})
    df = df.rename(columns=COLUMN_MAP)

    # coerce timestamp if present
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    # coerce price if present
    if "Price" in df.columns:
        # handle "1,500", "KSh 1,500", "1500.00", etc
    df["Price"] = (
    df["Price"]
    .astype(str)
    .str.replace(r"[^\d\.\-]", "", regex=True)
)
df["Price"] = pd.to_numeric(df["Price"], errors="coerce")

    return df


def validate_required(df_all: pd.DataFrame):
    missing = [c for c in REQUIRED if c not in df_all.columns]
    if missing:
        st.error(f"Missing columns: {missing}")
        st.stop()


# =========================
# UI
# =========================
st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

gc, SHEET_ID = get_gspread_client()
sh = gc.open_by_key(SHEET_ID)

# Load + standardize each tab
dfs = []
for item in STREAM_TABS:
    try:
        df = load_tab_df(sh, item["tab"])
        df = standardize_df(df, item["stream"])
        dfs.append({"meta": item, "df": df})
    except Exception as e:
        dfs.append({"meta": item, "df": pd.DataFrame(), "error": e})

# Show per-tab status
c1, c2, c3 = st.columns(3)

for col, pack in zip([c1, c2, c3], dfs):
    meta = pack["meta"]
    with col:
        st.subheader(meta["label"])
        if "error" in pack:
            st.error(f"{meta['label']} failed: {type(pack['error']).__name__}: {pack['error']}")
            continue

        df = pack["df"]
        st.write("Tab:", meta["tab"])
        st.metric("Rows", len(df))
        st.metric("Cols", len(df.columns))
        st.dataframe(df.head(10), use_container_width=True)

# Combine
df_all = pd.concat([p["df"] for p in dfs if "error" not in p], ignore_index=True)
validate_required(df_all)

st.divider()
st.subheader("All Streams (standardized)")

# Basic filters
min_d, max_d = None, None
if df_all["Timestamp"].notna().any():
    min_d = df_all["Timestamp"].min().date()
    max_d = df_all["Timestamp"].max().date()

left, right = st.columns(2)
with left:
    date_from = st.date_input("From", value=min_d or date.today())
with right:
    date_to = st.date_input("To", value=max_d or date.today())

mask = True
if "Timestamp" in df_all.columns and df_all["Timestamp"].notna().any():
    mask = (df_all["Timestamp"].dt.date >= date_from) & (df_all["Timestamp"].dt.date <= date_to)

df_f = df_all.loc[mask].copy()

# Metrics
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Rows (filtered)", len(df_f))
with m2:
    st.metric("Services (unique)", df_f["Service"].nunique(dropna=True))
with m3:
    st.metric("Total Price", float(df_f["Price"].fillna(0).sum()) if "Price" in df_f.columns else 0.0)

st.dataframe(df_f.sort_values("Timestamp", ascending=False), use_container_width=True)
