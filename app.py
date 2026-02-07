import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Ella Dashboard", layout="wide")
st.title("Ella Dashboard")

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

st.success("Connected to sheet ✅")
st.write("Sheet title:", sh.title)


