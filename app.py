import os, json, base64, re
from datetime import date
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# =========================
# CONFIG (Secrets)
# =========================
# Streamlit Secrets expected:
#   SHEET_ID = "...."
#   TAB_RECEP = "Form responses 1"   (or your exact tab name)
#   TAB_TECH  = "Form responses 2"
#   TAB_WAX_HUB = "Form responses 3"
#
# Auth (choose ONE):
#   GCP_SA_B64 = "<base64 of service_account.json>"   (recommended)
#   OR
#   gcp.service_account = { ...full json... }         (Streamlit built-in dict)
#
# Optional:
#   COMMISSION_RATE = 0.35


def _get_secret(key: str, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


SHEET_ID = _get_secret("SHEET_ID")
TAB_RECEP = _get_secret("TAB_RECEP", "Form responses 1")
TAB_TECH = _get_secret("TAB_TECH", "Form responses 2")
TAB_WAX_HUB = _get_secret("TAB_WAX_HUB", "Form responses 3")

COMMISSION_RATE = float(_get_secret("COMMISSION_RATE", 0.35))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


# =========================
# COLUMN MAPS (LOCKED)
# =========================
# We map "Google Form header" -> "internal column"
# Matching is case-insensitive and apostrophe-safe.

COLUMN_MAPS = {
    "Recep": {
        "timestamp": "Timestamp",
        "name": "Name",
        "phone number": "Phone",
        "service provider's name": "Tech",
        "service provided": "Service",
        "mode of payment": "PaymentMode",
        "comments": "Comments",
        "price": "Price",
        "payout (0.35)": "Payout",
        "payout": "Payout",
    },
    "Tech": {
        "timestamp": "Timestamp",
        "name": "Name",
        "phone number": "Phone",
        "service provider's name": "Tech",
        "service provided": "Service",
        "mode of payment": "PaymentMode",
        "comments": "Comments",
        "price": "Price",
        "payout (0.35)": "Payout",
        "payout": "Payout",
    },
    # ✅ Wax-Hub locked to your screenshot
    "Wax-Hub": {
        "timestamp": "Timestamp",
        "name": "Name",
        "phone number": "Phone",
        "service provider's name": "Tech",
        "service provided": "Service",
        "mode of payment": "PaymentMode",
        "comments": "Comments",
        "price": "Price",
        "payout (0.35)": "Payout",  # <-- your header
        "payout": "Payout",
    },
}

REQUIRED_INTERNAL = ["Timestamp", "Tech", "Service", "Price"]  # Payout can be computed


# =========================
# AUTH
# =========================
def get_credentials() -> Credentials:
    # Preferred: Base64 service account JSON
    sa_b64 = _get_secret("GCP_SA_B64", None)
    if sa_b64:
        sa_json = base64.b64decode(sa_b64).decode("utf-8")
        info = json.loads(sa_json)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    # Alternative: Streamlit native secret dict under [gcp] service_account
    try:
        info = st.secrets["gcp"]["service_account"]
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        raise RuntimeError(
            "Missing auth. Set GCP_SA_B64 in Streamlit Secrets (recommended), "
            "or set [gcp].service_account dict."
        )


@st.cache_resource
def get_gspread_client():
    creds = get_credentials()
    return gspread.authorize(creds)


@st.cache_resource
def open_sheet(sheet_id: str):
    gc = get_gspread_client()
    return gc.open_by_key(sheet_id)


# =========================
# HELPERS
# =========================
def canon(s: str) -> str:
    """canonicalize header: lowercase, strip, normalize apostrophes/spaces"""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("’", "'").replace("`", "'")
    s = re.sub(r"\s+", " ", s)
    return s


def standardize(df: pd.DataFrame, stream_name: str) -> pd.DataFrame:
    # 1) Canonicalize existing columns
    original_cols = list(df.columns)
    canon_to_original = {canon(c): c for c in original_cols}

    # 2) Rename using the stream map
    mapping = COLUMN_MAPS.get(stream_name, {})
    rename_map = {}
    for k, internal_name in mapping.items():
        kcanon = canon(k)
        if kcanon in canon_to_original:
            rename_map[canon_to_original[kcanon]] = internal_name

    df = df.rename(columns=rename_map)

    # 3) Normalize core types/values
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", dayfirst=True)

    if "PaymentMode" in df.columns:
        df["PaymentMode"] = (
            df["PaymentMode"]
            .astype(str)
            .str.strip()
            .str.replace(".", "", regex=False)  # Mpesa. -> Mpesa
        )

    if "Tech" in df.columns:
        df["Tech"] = df["Tech"].astype(str).str.strip()

    if "Service" in df.columns:
        df["Service"] = df["Service"].astype(str).str.strip()

    # Price numeric
    if "Price" in df.columns:
        df["Price"] = (
            df["Price"]
            .astype(str)
            .str.replace(r"[^\d\.\-]", "", regex=True)
        )
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")

    # Payout numeric (if present), else compute
    if "Payout" in df.columns:
        df["Payout"] = (
            df["Payout"]
            .astype(str)
            .str.replace(r"[^\d\.\-]", "", regex=True)
        )
        df["Payout"] = pd.to_numeric(df["Payout"], errors="coerce")
    else:
        if "Price" in df.columns:
            df["Payout"] = df["Price"] * COMMISSION_RATE

    return df


def validate_required(df: pd.DataFrame, stream_name: str):
    missing = [c for c in REQUIRED_INTERNAL if c not in df.columns]
    if missing:
        st.error(f"{stream_name}: Missing required columns after mapping: {missing}")
        st.stop()


# =========================
# LOAD
# =========================
@st.cache_data(ttl=300)
def load_tab(sheet_id: str, tab_name: str, stream_name: str) -> pd.DataFrame:
    sh = open_sheet(sheet_id)
    ws = sh.worksheet(tab_name)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df = standardize(df, stream_name)
    validate_required(df, stream_name)
    df["Stream"] = stream_name
    return df


def apply_filters(df: pd.DataFrame, tech, service, paymode, d1, d2) -> pd.DataFrame:
    out = df.copy()

    if "Timestamp" in out.columns:
        out = out[out["Timestamp"].notna()]
        out = out[(out["Timestamp"].dt.date >= d1) & (out["Timestamp"].dt.date <= d2)]

    if tech and tech != "All":
        out = out[out["Tech"] == tech]

    if service and service != "All":
        out = out[out["Service"] == service]

    if paymode and paymode != "All" and "PaymentMode" in out.columns:
        out = out[out["PaymentMode"] == paymode]

    return out


# =========================
# UI
# =========================
st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

if not SHEET_ID:
    st.error("Missing SHEET_ID in Streamlit Secrets.")
    st.stop()

streams = [
    ("Recep", TAB_RECEP),
    ("Tech", TAB_TECH),
    ("Wax-Hub", TAB_WAX_HUB),
]

# Load
dfs = []
for stream_name, tab in streams:
    try:
        dfs.append(load_tab(SHEET_ID, tab, stream_name))
    except Exception as e:
        st.error(f"{stream_name} failed: {type(e).__name__}: {e}")

if not dfs:
    st.stop()

df_all = pd.concat(dfs, ignore_index=True)

# Sidebar filters
st.sidebar.header("Filters")

min_date = df_all["Timestamp"].dt.date.min() if df_all["Timestamp"].notna().any() else date.today()
max_date = df_all["Timestamp"].dt.date.max() if df_all["Timestamp"].notna().any() else date.today()

d1, d2 = st.sidebar.date_input("Date range", value=(min_date, max_date))

tech_list = ["All"] + sorted([t for t in df_all["Tech"].dropna().unique() if str(t).strip() != ""])
service_list = ["All"] + sorted([s for s in df_all["Service"].dropna().unique() if str(s).strip() != ""])
paymode_list = ["All"]
if "PaymentMode" in df_all.columns:
    paymode_list += sorted([p for p in df_all["PaymentMode"].dropna().unique() if str(p).strip() != ""])

tech = st.sidebar.selectbox("Tech", tech_list, index=0)
service = st.sidebar.selectbox("Service", service_list, index=0)
paymode = st.sidebar.selectbox("Payment Mode", paymode_list, index=0)

# Split views
c1, c2, c3 = st.columns(3)

def render_stream(col, stream_name):
    with col:
        st.subheader(stream_name)
        df_s = df_all[df_all["Stream"] == stream_name]
        df_f = apply_filters(df_s, tech, service, paymode, d1, d2)

        total_price = float(df_f["Price"].fillna(0).sum()) if "Price" in df_f.columns else 0.0
        total_payout = float(df_f["Payout"].fillna(0).sum()) if "Payout" in df_f.columns else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Rows", len(df_f))
        m2.metric("Total Price", f"{total_price:,.0f}")
        m3.metric("Total Payout", f"{total_payout:,.0f}")

        st.dataframe(
            df_f.sort_values("Timestamp", ascending=False).head(200),
            use_container_width=True
        )

render_stream(c1, "Recep")
render_stream(c2, "Tech")
render_stream(c3, "Wax-Hub")

st.divider()
st.subheader("All Streams (combined)")

df_comb = apply_filters(df_all, tech, service, paymode, d1, d2)
total_price_all = float(df_comb["Price"].fillna(0).sum()) if "Price" in df_comb.columns else 0.0
total_payout_all = float(df_comb["Payout"].fillna(0).sum()) if "Payout" in df_comb.columns else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", len(df_comb))
m2.metric("Total Price", f"{total_price_all:,.0f}")
m3.metric("Total Payout", f"{total_payout_all:,.0f}")
m4.metric("Avg Ticket", f"{(total_price_all/len(df_comb)) if len(df_comb) else 0:,.0f}")

st.dataframe(
    df_comb.sort_values("Timestamp", ascending=False),
    use_container_width=True
)
