import streamlit as st
from PIL import Image
import PyPDF2
import io
import time
from datetime import datetime
import openai
import base64
import uuid
import pandas as pd
import psycopg2
from psycopg2 import sql
from pdf2image import convert_from_bytes

# Streamlit page configuration
st.set_page_config(page_title="Document Upload Portal", layout="wide")

# Database connection using Streamlit secrets
connection = psycopg2.connect(
    host=st.secrets["db_host"],
    database=st.secrets["db_database"],
    user=st.secrets["db_user"],
    password=st.secrets["db_password"]
)
cursor = connection.cursor()

def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Load CSS
load_css('styles2.css')

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def get_dropdown_names(TicketType):
    if TicketType == "Income":
        return ["Payslip", "Bank Statement"]
    elif TicketType == "KYC":
        return ["Passport", "Driving License"]
    elif TicketType == "KYC and Income":
        return ["Payslip", "Bank Statement", "Passport", "Driving License"]

def get_ticket_type(ticket_id):
    if not ticket_id or not is_valid_uuid(ticket_id):
        return None
    
    query = sql.SQL("SELECT ticket_type FROM obf_tickets WHERE id = %s")
    try:
        cursor.execute(query, (ticket_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except psycopg2.Error as e:
        st.error(f"Database error: {e}")
        return None

def get_document_details(ticket_id):
    query = """
    SELECT document_link, verification_response
    FROM obf_documents
    WHERE ticket_id = %s
    """
    cursor.execute(query, (ticket_id,))
    result = cursor.fetchall()
    document_links = [row[0] for row in result]
    document_responses = [row[1] for row in result]
    return document_links, document_responses

def get_uuid(ticket_id):
    query = "SELECT user_id FROM obf_tickets WHERE id = %s"
    cursor.execute(query, (ticket_id,))
    result = cursor.fetchone()
    return result[0] if result else "UUID not found."

def save_uploaded_file(uploaded_file, folder_path, save_name):
    if uploaded_file and save_name:
        original_filename = uploaded_file.name
        _, file_extension = os.path.splitext(original_filename)
        if not os.path.splitext(save_name)[1]:
            save_name += file_extension
        # Save to temporary file
        with open(save_name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return save_name
    return None

def verify_document(document_type, file_path, first_name, last_name):
    if document_type == "Passport":
        return passport_verify(file_path, first_name, last_name)
    elif document_type == "Driving License":
        return license_verify(file_path, first_name, last_name)
    elif document_type == "Payslip":
        return checkpayslip(file_path)
    elif document_type == "Bank Statement":
        return checkbankstatement(file_path)
    return "Invalid document type."

def remove_extension(file_path):
    return os.path.splitext(file_path)[0]

def create_document(doc_path, ticketid, document_type, verification_result, user_id):
    document = {
        "Document No": str(uuid.uuid4()),
        "Ticket ID": ticketid,
        "Document Link": doc_path,
        "Document Name": document_type,
        "Verification Response": "",
        "User ID": user_id
    }
    if verification_result == 1:
        document["Verification Response"] = "Verified"
    elif verification_result == 0:
        document["Verification Response"] = "Reupload"
    elif verification_result == -1:
        document["Verification Response"] = "Incorrect Document"

    check_query = """
    SELECT id FROM obf_documents WHERE ticket_id = %s AND user_id = %s AND document_link LIKE %s
    """
    doc_link_base = remove_extension(document["Document Link"])
    cursor.execute(check_query, (ticketid, user_id, f"{doc_link_base}%"))
    existing_document = cursor.fetchone()

    if existing_document:
        update_query = """
        UPDATE obf_documents
        SET document_name = %s, document_link = %s, verification_response = %s, ticket_id = %s, user_id = %s, modified_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        cursor.execute(update_query, (
            document["Document Name"], document["Document Link"], document["Verification Response"],
            document["Ticket ID"], document["User ID"], existing_document[0]
        ))
    else:
        insert_query = """
        INSERT INTO obf_documents (document_name, document_link, verification_response, ticket_id, user_id, created_at, modified_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        cursor.execute(insert_query, (
            document["Document Name"], document["Document Link"], document["Verification Response"],
            document["Ticket ID"], document["User ID"]
        ))
    connection.commit()

def update_tickets(ticket_id, document_responses):
    all_verified = all(response == "Verified" for response in document_responses)

    update_query = """
        UPDATE obf_tickets
        SET all_documents_submitted = TRUE
        WHERE id = %s;
    """
    cursor.execute(update_query, (ticket_id,))

    if all_verified:
        update_status_query = """
        UPDATE obf_tickets
        SET status = 'Resolved'
        WHERE id = %s;
        """
        cursor.execute(update_status_query, (ticket_id,))

    connection.commit()

def get_ticket_id_from_url():
    return st.experimental_get_query_params().get("ticket_id", [None])[0]

def main():
    st.image("https://cdn.asp.events/CLIENT_CL_Conf_BDA05934_5056_B731_4C9EEBBE0C2416C2/sites/PayExpo-2020/media/libraries/sponsor/Modulr-Logo-CMYK-420x155.png/fit-in/700x9999/filters:no_upscale()", width=200)
    st.title("Document Validator")
    st.markdown(
        """
        <div class="footer">
            Disclaimer: All documents used in this demo are either AI-generated or pseudonymized.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if "last_uploaded_file" not in st.session_state:
        st.session_state.last_uploaded_file = None

    # Get ticket_id from URL parameter
    url_ticket_id = get_ticket_id_from_url()

    col1, col2 ,col3,col4 = st.columns([3,1,2,1])
    with col4:st.markdown("")
    with col3:st.markdown("")
    with col1:
        # Auto-populate ticket ID if available in URL
        ticket_id = st.text_input("Enter your Ticket ID:", value=url_ticket_id, key="ticket_id")
        
        if ticket_id:
            ticket_type = get_ticket_type(ticket_id)
            if ticket_type:
                document_type = st.selectbox(
                    "Select document type", get_dropdown_names(ticket_type)
                )
                uploaded_doc = st.file_uploader(
                    "Upload your document", type=["pdf", "png", "jpg", "jpeg"]
                )
            else:
                st.error("Invalid Ticket ID. Please enter a valid Ticket ID.")
                return  # Exit the function if ticket ID is invalid
        else:
            st.warning("Please enter a Ticket ID to proceed.")
            return  # Exit the function if no ticket ID is provided
    
        if uploaded_doc is not None:
            file_type = uploaded_doc.type
            # Preview for image files
            with col3:
                if file_type in ["image/jpeg", "image/jpg", "image/png"]:
                    st.text("Image Preview:")
                    image = Image.open(uploaded_doc)
                    st.image(image, caption="Uploaded Image", use_column_width=True)
                # Preview for PDF files
                elif file_type == "application/pdf":
                    st.text("PDF Preview:")
                    try:
                        # Convert the first page of the PDF to an image
                        pdf_pages = convert_from_bytes(uploaded_doc.getvalue(), first_page=0, last_page=1)
                        if pdf_pages:
                            st.image(pdf_pages[0], caption="First page of PDF", use_column_width=True)
                        
                        # Get additional information about the PDF
                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_doc.getvalue()))
                        num_pages = len(pdf_reader.pages)
                        st.write(f"Number of pages: {num_pages}")
                    except Exception as e:
                        st.error(f"Error processing PDF: {str(e)}")

            if uploaded_doc != st.session_state.last_uploaded_file:
                file_path = save_uploaded_file(
                    uploaded_doc, "tmp", f"{uuid.uuid4()}"
                )
                st.session_state.last_uploaded_file = uploaded_doc

                verification_result = verify_document(
                    document_type, file_path, "Mona", "Lisa"
                )
                create_document(file_path, ticket_id, document_type, verification_result, get_uuid(ticket_id))

                time.sleep(3)
                
                if verification_result == -1:
                    st.error(
                        f"This does not seem to be a valid {document_type.lower()}. Please reupload the requested document."
                    )
                elif verification_result == 0:
                    st.warning(
                        f"Unable to verify your details. Please reupload {document_type.lower()} with correct details."
                    )
                elif verification_result == 1:
                    st.success(f"{document_type} Verification Successful.")
                    st.toast(f"{document_type} verified successfully!", icon="✅")
                else:
                    st.info("Unexpected result from verification.")
            else:
                st.info("No new file uploaded, or file already saved.")

        if st.button("All documents submitted", key="all_submitted"):
            try:
                document_links, document_responses = get_document_details(ticket_id)
                update_tickets(
                    ticket_id=ticket_id,
                    document_responses=document_responses
                )
                st.success("Documents submitted successfully!")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
