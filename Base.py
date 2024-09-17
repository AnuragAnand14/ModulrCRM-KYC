import streamlit as st
import pandas as pd
import uuid
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from email.mime.text import MIMEText
from twilio.rest import Client
import psycopg2
from psycopg2.extras import RealDictCursor
import base64

# Retrieve environment variables from Streamlit secrets
DB_HOST = st.secrets["DB_HOST"]
DB_NAME = st.secrets["DB_NAME"]
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Twilio setup
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Twilio setup
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# PostgreSQL connection
def get_db_connection():
    return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

# Set page config for wide layout
st.set_page_config(page_title="CRM", layout="wide")

st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .main {
        padding: 1rem;
    }
    h1, h2, h3, h4 {
        color: #000000;
        margin-bottom: 0.5rem;
    }
    .stButton > button {
        width: 100%;
        padding: 0.5rem;
        font-size: 0.85rem;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #2563EB;
    }
    .customer-card {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    .customer-info {
        margin-bottom: 0.5rem;
    }
    .ticket-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .ticket-card {
        background-color: #f8fafc;
        padding: 0.75rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .ticket-header {
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .ticket-info {
        margin-bottom: 0.25rem;
        font-size: 0.9rem;
    }
    .contact-buttons {
        display: flex;
        gap: 0.5rem;
    }
    .contact-buttons .stButton {
        flex: 1;
    }
    .stExpanderHeader {
        font-weight: bold;
        font-size: 1.1rem;
        color: #1E3A8A;
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 10px;
    }
    .stExpander {
        border-radius: 8px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        margin-top: 20px;
    }
    .dataframe-container {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        overflow: hidden;
        margin-top: 10px;
    }
    .dataframe-table th {
        background-color: #1E3A8A !important;
        color: white !important;
        font-weight: bold !important;
        font-size: 18px !important;
        padding: 10px !important;
        border-bottom: 1px solid #ddd !important;
    }
    .dataframe-table td {
        padding: 8px !important;
        font-size: 18px !important;
        color: #333 !important;
        border-bottom: 1px solid #ddd !important;
    }
</style>
""", unsafe_allow_html=True)


def get_gmail_service():
    creds = None
    if 'token' in st.session_state:
        creds = Credentials.from_authorized_user_info(eval(st.session_state['token']), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # For Streamlit Cloud, we'll use service account credentials
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPES
            )
        st.session_state['token'] = str(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_document_table(verification_type):
    documents = {
        "Income": [
            "Payslip",
            "Bank Statement"
        ],
        "Fraud": [
            "Passport",
            "Driving License"
        ],
        "Both": [
            "Payslip",
            "Bank Statement",
            "Passport",
            "Driving License"
        ],
        "Default": [
            "Payslip",
            "Bank Statement",
            "Passport",
            "Driving License"
        ]
    }
    doc_list = documents.get(verification_type, documents["Default"])
    table = "Required Documents: \n"
    for doc in doc_list:
        table += f" -> {doc} \n"
    return table

def send_email(to_email, subject, body):
    service = get_gmail_service()
    message = MIMEText(body)
    message['to'] = to_email
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    try:
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def create_ticket(row):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO obf_tickets (user_id, ticket_type, created_at, status, comments)
            VALUES (%s, %s, NOW(), 'Pending', %s)
            RETURNING id, ticket_type, created_at, status
        """, (row['id'], row['ticket_type'], "Awaiting document upload"))
        ticket = cur.fetchone()
        conn.commit()
        return ticket
    finally:
        cur.close()
        conn.close()

def fetch_tickets():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM obf_tickets WHERE deleted_at IS NULL")
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def send_whatsapp_message(to_number, message):
    try:
        from_number = 'whatsapp:+14155238886'  # Your Twilio WhatsApp-enabled number
        message = twilio_client.messages.create(
            body=message,
            from_=from_number,
            to=f'whatsapp:{to_number}'
        )
        return True, f"WhatsApp message sent successfully. SID: {message.sid}"
    except Exception as e:
        return False, f"Error sending WhatsApp message: {e}"

def send_trigger_to_all(df):
    for _, row in df.iterrows():
        ticket = create_ticket(row)
        unique_link = f"https://mjd3mtr4-8502.inc1.devtunnels.ms/?ticket_id={ticket['id']}"
        
        verification_type = row.get('verification_type', row.get('product_type', 'Default'))
        doc_table = get_document_table(verification_type)
        
        message = f"""Hi {row['first_name']} {row['last_name']},

We have reviewed your application for {verification_type} verification and request you to upload the following documents to proceed further:

{doc_table}

Please use this link to upload: {unique_link}

Your ticket number is: {ticket['id']}

Thank you"""
        
        if send_email(row['email'], "Document Upload Request", message):
            st.success(f"Email sent to {row['email']}!")
        
        success, result = send_whatsapp_message(row['phone_number'], message)
        if success:
            st.success(f"WhatsApp Reminder Sent to {row['first_name']}!")
        else:
            st.error(result)

def main():
    col1, col2 = st.columns([1, 6])
    with col1:
        st.image("https://www.blenheimchalcot.com/wp-content/uploads/2018/07/modulr-finance-limited-logo-vector.svg", width=200)
    with col2:
        st.title("Customer Relationship Management Portal")
    st.markdown("---")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM obf_users WHERE deleted_at IS NULL AND is_active = TRUE")
        df = pd.DataFrame(cur.fetchall())
        st.success("Customer Details Fetched Successfully")
    except Exception as e:
        st.error(f"Error Loading Customer Data: {e}")
        return
    finally:
        cur.close()
        conn.close()

    tickets = fetch_tickets()

    if st.button("Contact All Users"):
        send_trigger_to_all(df)

    st.subheader("Customer Details")
    for _, row in df.iterrows():
        with st.container():
            st.markdown('<div class="customer-card">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f'<div class="customer-info"><strong>{row["first_name"]} {row["last_name"]}</strong></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="customer-info"><strong>Email:</strong> {row["email"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="customer-info"><strong>Phone:</strong> {row["phone_number"]}</div>', unsafe_allow_html=True)
            with col2:
                verification_type = row.get('verification_type', row.get('product_type', 'Unknown'))
                st.markdown(f'<div class="customer-info"><strong>Verification Type:</strong> {verification_type}</div>', unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="contact-buttons">', unsafe_allow_html=True)
                if st.button("Contact via Email", key=f"email_{row['id']}"):
                    ticket = create_ticket(row)
                    unique_link = f"https://mjd3mtr4-8502.inc1.devtunnels.ms/?ticket_id={ticket['id']}"
                    verification_type = row.get('verification_type', row.get('product_type', 'Default'))
                    doc_table = get_document_table(verification_type)
                    
                    email_body = f"""Hi {row['first_name']} {row['last_name']},

We have reviewed your application for onboarding at Modulr.Please proceed for {verification_type} verification. Upload the following documents to proceed further:

{doc_table}

Please use this link to upload: {unique_link}
Your ticket number is: {ticket['id']}

Thank you"""
                    
                    if send_email(row['email'], "Document Upload Request", email_body):
                        st.success(f"Email sent to {row['email']}!")
                
                if st.button("Contact via WhatsApp", key=f"whatsapp_{row['id']}"):
                    ticket = create_ticket(row)
                    unique_link = f"https://mjd3mtr4-8502.inc1.devtunnels.ms/?ticket_id={ticket['id']}"
                    verification_type = row.get('verification_type', row.get('product_type', 'Default'))
                    doc_table = get_document_table(verification_type)
                    
                    whatsapp_message = f"""Hi {row['first_name']} {row['last_name']},

We have reviewed your application for {verification_type} verification and request you to upload the following documents to proceed further:

{doc_table}

Please use this link to upload: {unique_link}

Your ticket number is: {ticket['id']}

Thank you"""
                    
                    success, result = send_whatsapp_message(row['phone_number'], whatsapp_message)
                    if success:
                        st.success(f"WhatsApp Reminder Sent to {row['first_name']}!")
                    else:
                        st.error(result)

            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
