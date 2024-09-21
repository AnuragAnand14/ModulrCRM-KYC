
import os
from email.mime.text import MIMEText
import smtplib
from email.mime.multipart import MIMEMultipart
import ssl
import certifi
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables from .env file
load_dotenv("myenv/.env")
st.set_page_config(page_title="CRM", layout="wide")

# Retrieve environment variables
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')

# Gmail API setup
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


# CSS styling
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
    .sidebar .company-button {
        width: 100%;
        margin-bottom: 10px;
        color: white;
        border: none;
        padding: 10px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 4px;
    }
    .sidebar .obf-button {
        background-color: #3B82F6;
    }
    .sidebar .modulr-button {
        background-color: black;
    }
    .sidebar .salary-finance-button {
        background-color: #FF6B6B;
    }
    .company-button:hover {
        opacity: 0.8;
    }
    .sidebar .company-button {
        width: 100%;
        margin-bottom: 10px;
    }
    
</style>
""", unsafe_allow_html=True)


def get_document_table(product_type):
    # Define document requirements based on the product_type
    documents = {
        "Income": [
            "Payslip",
            "Bank Statement"
        ],
        "POI": [
            "Passport",
            "Driving License"
        ],
        "income and POI": [
            "Payslip",
            "Bank Statement",
            "Passport",
            "Driving License"
        ],
        # Add a default list for unknown verification types
        "Default": [
            "Payslip",
            "Bank Statement",
            "Passport",
            "Driving License"
        ]
    }

    # Get the document list based on the product_type
    doc_list = documents.get(product_type, documents["Default"])

    # Format the document table
    table = "Required Documents: \n"
    for doc in doc_list:
        table += f" -> {doc} \n"

    return table



def send_email(to_email, subject, body):
    smtp_server = "smtp.gmail.com"  # Gmail's SMTP server (or your preferred SMTP server)
    smtp_port = 465  # For SSL
    sender_email = "mteam8826@gmail.com"
    sender_password = "cypi hvja csyq abcs"  # Use an app password if using Gmail

    # Create the email
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = to_email
    message['Subject'] = subject

    # Attach the body to the email
    message.attach(MIMEText(body, 'plain'))

    # Try to send the email
    try:
        # Create an SSL context with a manually specified CA bundle
        context = ssl.create_default_context(cafile=certifi.where())

        # Connect to the SMTP server and send the email
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
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


def fetch_tickets(company):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Construct the query to join obf_tickets with obf_users
        query = """
        SELECT t.*
        FROM obf_tickets t
        JOIN obf_users u ON t.user_id = u.id
        WHERE t.deleted_at IS NULL
        AND u.company = %s
        """
        cur.execute(query, (company,))
        return cur.fetchall()
    except Exception as e:
        print(f"Error fetching tickets: {e}")
        return []
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


def get_company_specific_link(company, ticket_id):
    base_urls = {
        "OBF": "https://obfdocvalidator.streamlit.app",
        "Modulr": "https://modulr-doc-validator-e0c8fucjbwe2edef.uksouth-01.azurewebsites.net",
        "Salary Finance": "https://salaryfinanacedocvalidator.streamlit.app"
    }
    base_url = base_urls.get(company, "https://default-validator.example.com")
    return f"{base_url}/?ticket_id={ticket_id}"


def get_company_specific_message(company, row, ticket, unique_link):
    verification_type = row.get('verification_type', row.get('product_type', 'Default'))
    doc_table = get_document_table(verification_type)

    if company == "OBF":
        return f"""Hi {row['first_name']} {row['last_name']},

OakBrook Finance has reviewed your application for a Loan and we would like to proceed with {verification_type} verification. To continue with the process, kindly upload the required documents listed below:

{doc_table}

Upload link: {unique_link}
Ticket number: {ticket['id']}

Thank you for choosing OakBrook Finance. We look forward to assisting you further."""

    elif company == "Modulr":
        return f"""Dear {row['first_name']} {row['last_name']},

Modulr has processed your onboarding application. For {verification_type} verification, we require the following documents:

{doc_table}

Please use this secure link to upload: {unique_link}
Your reference number is: {ticket['id']}

We appreciate your cooperation in ensuring a smooth onboarding process.

Best regards,
Modulr Team"""

    elif company == "Salary Finance":
        return f"""Hello {row['first_name']} {row['last_name']},

Salary Finance is now  ready to onboard you. Kindly proceed with your {verification_type} verification. Please submit the following documents:

{doc_table}

Secure upload link: {unique_link}
Case ID: {ticket['id']}

If you have any questions, our support team is here to help.

Warm regards,
Salary Finance Team"""

    else:
        return f"""Hi {row['first_name']} {row['last_name']},

We have reviewed your application for {verification_type} verification and request you to upload the following documents:

{doc_table}

Please use this link to upload: {unique_link}
Your ticket number is: {ticket['id']}

Thank you"""


def send_trigger_to_all(df, company):
    for _, row in df.iterrows():
        ticket = create_ticket(row)
        unique_link = get_company_specific_link(company, ticket['id'])

        message = get_company_specific_message(company, row, ticket, unique_link)

        if send_email(row['email'], f"Document Upload Request - {company}", message):
            st.success(f"Email sent to {row['email']}!")

        success, result = send_whatsapp_message(row['phone_number'], message)
        if success:
            st.success(f"WhatsApp Reminder Sent to {row['first_name']}!")
        else:
            st.error(result)


def display_main_content(company):
    # Load data from the database
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

    # Fetch tickets from the database
    tickets = fetch_tickets(company)

    # Button to send trigger to all
    if st.button("Contact All Users"):
        send_trigger_to_all(df, company)

    # Display all customer details with individual trigger buttons
    st.subheader("Customer Details")
    for _, row in df.iterrows():
        with st.container():
            st.markdown('<div class="customer-card">', unsafe_allow_html=True)

            # Customer info and trigger buttons
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f'<div class="customer-info"><strong>{row["first_name"]} {row["last_name"]}</strong></div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="customer-info"><strong>Email:</strong> {row["email"]}</div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="customer-info"><strong>Phone:</strong> {row["phone_number"]}</div>',
                            unsafe_allow_html=True)
            with col2:
                verification_type = row.get('verification_type', row.get('product_type', 'Unknown'))
                st.markdown(f'<div class="customer-info"><strong>Verification Type:</strong> {verification_type}</div>',
                            unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="contact-buttons">', unsafe_allow_html=True)
                if st.button("Contact via Email", key=f"email_{row['id']}"):
                    ticket = create_ticket(row)
                    unique_link = get_company_specific_link(company, ticket['id'])

                    email_body = get_company_specific_message(company, row, ticket, unique_link)

                    if send_email(row['email'], f"Document Upload Request - {company}", email_body):
                        st.success(f"Email sent to {row['email']}!")

                if st.button("Contact via WhatsApp", key=f"whatsapp_{row['id']}"):
                    ticket = create_ticket(row)
                    unique_link = get_company_specific_link(company, ticket['id'])

                    whatsapp_message = get_company_specific_message(company, row, ticket, unique_link)

                    success, result = send_whatsapp_message(row['phone_number'], whatsapp_message)
                    if success:
                        st.success(f"WhatsApp message sent to {row['phone_number']}!")
                    else:
                        st.error(result)
                st.markdown('</div>', unsafe_allow_html=True)

            # Display tickets related to the current customer in a grid format
            customer_tickets = [ticket for ticket in tickets if ticket["user_id"] == row['id']]
            if customer_tickets:
                st.markdown('<div class="ticket-grid">', unsafe_allow_html=True)
                cols = st.columns(3)  # Create 3 columns for the grid
                for idx, ticket in enumerate(customer_tickets):
                    with cols[idx % 3]:  # Distribute tickets across the columns
                        st.markdown(f"""
                        <div class="ticket-card">
                            <div class="ticket-header">Ticket No: {ticket["id"]}</div>
                            <div class="ticket-info"><strong>Created At:</strong> {ticket["created_at"]}</div>
                            <div class="ticket-info"><strong>Status:</strong> {ticket["status"]}</div>
                        </div>
                        """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # Display the tickets in a collapsible format
    with st.expander("View All Ticket Updates", expanded=False):
        st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
        try:
            df_tickets = pd.DataFrame(tickets)
            st.dataframe(df_tickets.style.set_properties(**{
                'background-color': '#f0f2f6',
                'color': '#333',
                'border-color': 'white'
            }).set_table_styles([
                {'selector': 'thead th',
                 'props': [('background-color', '#1E3A8A'), ('color', 'white'), ('font-weight', 'bold')]},
                {'selector': 'tbody td', 'props': [('padding', '10px'), ('border-bottom', '1px solid #ddd')]}
            ]))
        except Exception as e:
            st.error(f"Error loading ticket data: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

def main():
        if 'selected_company' not in st.session_state:
            st.session_state.selected_company = None

        # Move company selection to sidebar with styled buttons
        st.sidebar.title("Company Selection")

        if st.sidebar.button("OBF", key="obf_button", help="Select OBF", use_container_width=True):
            st.session_state.selected_company = "OBF"

        if st.sidebar.button("Modulr", key="modulr_button", help="Select Modulr", use_container_width=True):
            st.session_state.selected_company = "Modulr"

        if st.sidebar.button("Salary Finance", key="salary_finance_button", help="Select Salary Finance",
                             use_container_width=True):
            st.session_state.selected_company = "Salary Finance"

    # Main content area

        col1, col2 = st.columns([1, 8])
        with col2:
            st.title("Customer Relationship Management Portal")
        with col1:
            st.image("https://logovtor.com/wp-content/uploads/2021/08/blenheim-chalcot-logo-vector.png", width=125)


        # Display main content if a company is selected
        if st.session_state.selected_company:
            st.write(f"Selected Portfolio: **{st.session_state.selected_company}**")
            display_main_content(st.session_state.selected_company)
        else:
            st.write("Please select a Portfolio from the sidebar to view customer data.")

if __name__ == "__main__":
    main()