import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials


def connect_to_sheets_by_id(spreadsheet_id):
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scopes)
    gc = gspread.authorize(creds)
    spreadsheet_id = st.secrets["spreadsheet_id"]
    spreadsheet = gc.open_by_key(spreadsheet_id)
    return spreadsheet


def get_dataframe(worksheet):
    return pd.DataFrame(worksheet.get_all_records())


def update_dataframe(worksheet,df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())
