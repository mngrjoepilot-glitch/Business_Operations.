import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

SHEET_ID = "144GXa99ETKAMXvY6i9IELvmF7gF0U07ta2Z-IbIEN38"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES
)

gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

st.title("E.N.P OPERATIONAL KPIs")

tabs = {
    "Recep": "Form Responses 1",
    "Tech": "Form responses 2",
    "Wax-Hub": "Form responses 3"
}

tab_name = st.selectbox("Select tab", list(tabs.keys()))
ws = sh.worksheet(tabs[tab_name])

df = pd.DataFrame(ws.get_all_records())
st.dataframe(df)
