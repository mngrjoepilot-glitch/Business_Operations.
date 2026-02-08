# app.py
# Ella Nails / Wax Hub dashboard (3 tabs + combined)
#
# Streamlit Secrets (ONLY):
#   SHEET_ID   = "your_google_sheet_id"
#   GCP_SA_B64 = "base64(service_account.json)"   (single line)
#
# Column letters you gave (Google Sheets 1-based):
#   Form Responses 1: Price=L(12), Payout=M(13)
#   Form responses 2: Price=N(14), Payout=O(15)
#   Form responses 3: Price=H(8),  Payout=I(9)
#
# Python indexing is 0-based -> we use (col_number - 1)

import base64
import json
import re
from datetime import date

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# =========================
# CONFIG
# =========================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

TAB_RECEP = "Form Responses 1"
TAB_TECH = "Form responses 2"
TAB_WAX_HUB = "Form responses 3"

STREAM_TABS = [
    {"label": "Recep",   "tab": TAB_RECEP,   "stream": "Recep",   "price_col": 12, "payout_col": 13},
    {"label": "Tech",    "tab": TAB_TECH,    "stream": "Tech",    "price_col": 14, "payout_col": 15},
    {"label": "Wax-Hub", "tab": TAB_WAX_HUB, "stream": "Wax-Hub", "price_col": 8,  "payout_col": 9},
]

STANDARD_COLUMNS = ["Timestamp", "Service Provider", "Service", "Mode of Payment", "Price", "Payout", "Stream"]

COLUMN_MAP = {
    "timestamp": "Timestamp",
    "time stamp": "Timestamp",
    "date": "Timestamp",

    "service provider": "Service Provider",
    "service provider's name": "Service Provider",
    "service providers name": "Service Provider",
    "technician": "Service Provider",
    "tech": "Service Provider",
    "staff": "Service Provider",

    "service": "Service",
    "service provided": "Service",
    "services": "Service",

    "mode of payment": "Mode of Payment",
    "payment mode": "Mode of Payment",
    "payment": "Mode of Payment",

    "price": "Price",
    "amount": "Price",
    "service cost": "Price",

    "payout": "Payout",
    "technician payout": "Payout",
    "commission": "Payout",
    "salary": "Payout",
}


# =========================
# HELPERS
# =========================
def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h).strip().lower())


def _make_unique_headers(headers: list[str]) -> list[str]:
    seen = {}
    out = []
    for h in headers:
        h0 = str(h).strip()
        if h0 == "":
            h0 = "Unnamed"
        n = seen.get(h0, 0) + 1
        seen[h0] = n
        out.append(h0 if n == 1 else f"{h0}__{n}")
    return out


def _get_creds() -> Credentials:
    sa_json_str = base64.b64decode(st.secrets["GCP_SA_B64"]).decode("utf-8")
    sa_info = json.loads(sa_json_str)
    return Credentials.from_service_account_info(sa_info, scopes=SCOPES)


@st.cache_resource(show_spinner=False)
def _get_sheet():
    sheet_id = st.secrets.get("SHEET_ID", "").strip()
    if not SHEET_ID:
        st.error("Missing SHEET_ID in Streamlit secrets.")
        st.stop()
    creds = _get_creds()
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def load_tab(tab_name: str) -> pd.DataFrame:
    sh = _get_sheet()
    ws = sh.worksheet(tab_name)
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()

    headers = _make_unique_headers(values[0])
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    df = df.replace("", pd.NA).dropna(how="all")
    return df


def _money_to_num(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce")


def standardize_df(df: pd.DataFrame, meta: dict) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # rename by known headers
    rename_map = {}
    for c in df.columns:
        key = _normalize_header(c)
        if key in COLUMN_MAP:
            rename_map[c] = COLUMN_MAP[key]
    df = df.rename(columns=rename_map)

    # ensure standard columns exist
    for c in STANDARD_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA

    # Timestamp
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    # Fallback by Google Sheets column number (1-based) -> Python index (0-based)
    p_i = meta["price_col"] - 1
    po_i = meta["payout_col"] - 1

    # Pull raw by position regardless of header problems
    if df.shape[1] > p_i:
        df["Price"] = df.iloc[:, p_i]
    if df.shape[1] > po_i:
        df["Payout"] = df.iloc[:, po_i]

    # Clean money
    df["Price"] = _money_to_num(df["Price"])
    df["Payout"] = _money_to_num(df["Payout"])

    # Stream label
    df["Stream"] = meta["stream"]

    return df[STANDARD_COLUMNS]


def show_stream(col, meta: dict) -> pd.DataFrame:
    with col:
        st.subheader(meta["label"])
        try:
            raw = load_tab(meta["tab"])
            df = standardize_df(raw, meta)

            st.caption(f"Tab: {meta['tab']}")
            st.metric("Rows", int(len(df)))
            st.metric("Cols", int(len(df.columns)))

            st.metric("Total Sales", f"{float(df['Price'].fillna(0).sum()):,.0f}")
            st.metric("Total Payout", f"{float(df['Payout'].fillna(0).sum()):,.0f}")

            st.dataframe(df.head(15), use_container_width=True)
            return df

        except gspread.exceptions.WorksheetNotFound:
            st.error(f"WorksheetNotFound: {meta['tab']}")
            return pd.DataFrame(columns=STANDARD_COLUMNS)
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
            return pd.DataFrame(columns=STANDARD_COLUMNS)


# =========================
# UI
# =========================
st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

c1, c2, c3 = st.columns(3)
df_rece = show_stream(c1, STREAM_TABS[0])
df_tech = show_stream(c2, STREAM_TABS[1])
df_wax = show_stream(c3, STREAM_TABS[2])

st.divider()
st.header("All Streams (combined)")

df_all = pd.concat([df_rece, df_tech, df_wax], ignore_index=True)
if df_all.empty:
    st.warning("No data loaded.")
    st.stop()

with st.expander("Filters", expanded=True):
    streams = sorted(df_all["Stream"].dropna().unique().tolist())
    selected_streams = st.multiselect("Stream", options=streams, default=streams)
    df_f = df_all[df_all["Stream"].isin(selected_streams)].copy()

    if df_f["Timestamp"].notna().any():
        dmin = df_f["Timestamp"].min().date()
        dmax = df_f["Timestamp"].max().date()
        dr = st.date_input("Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(dr, tuple) and len(dr) == 2:
            start_d, end_d = dr
            df_f = df_f[(df_f["Timestamp"].dt.date >= start_d) & (df_f["Timestamp"].dt.date <= end_d)]
    else:
        st.info("No valid Timestamp values to filter by date.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Rows", int(len(df_f)))
k2.metric("Total Sales", f"{float(df_f['Price'].fillna(0).sum()):,.0f}")
k3.metric("Total Payout", f"{float(df_f['Payout'].fillna(0).sum()):,.0f}")
k4.metric("Unique Providers", int(df_f["Service Provider"].dropna().nunique()))

st.subheader("Summary by Service Provider")
prov = (
    df_f.dropna(subset=["Service Provider"])
        .groupby(["Stream", "Service Provider"], as_index=False)
        .agg(
            Jobs=("Service", "count"),
            Sales=("Price", "sum"),
            Payout=("Payout", "sum"),
        )
        .sort_values(["Sales", "Jobs"], ascending=False)
)
st.dataframe(prov, use_container_width=True)

st.subheader("Detailed Records")
st.dataframe(df_f.sort_values("Timestamp", ascending=False), use_container_width=True)
