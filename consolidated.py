import streamlit as st
from PIL import Image
import PyPDF2
import os
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import fitz
import base64
from io import BytesIO
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field
import uuid
import pandas as pd
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse, parse_qs
from pdf2image import convert_from_bytes
import io
from dotenv import load_dotenv
def load_secrets():
  secrets = st.secrets["document_validator"]     
  return secrets

secrets = load_secrets()

# Database connection
connection = psycopg2.connect(
    host=secrets["database_host"],
    database=secrets["database_name"],
    user=secrets["database_user"],
    password=secrets["database_password"]
)
cursor = connection.cursor()

# Set up OpenAI API key
openai.api_key = secrets["openai_api_key"]
os.environ["OPENAI_API_KEY"] = secrets["openai_api_key"]
st.set_page_config(page_title="OBF", layout="wide")


# Helper functions
st.markdown("""
<style>
.stApp {
    background-color: #ffffff;
    font-family: 'Roboto', sans-serif;
}



/* Divider */
.stApp hr {
    border-top: 2px solid #3498db;
    margin: 2rem 0;
}
/* Input fields */
.stTextInput > div > div > input {
    border: 2px solid #278ccf;
    border-radius: 5px;
    padding: 0.5rem;
    font-size: 1rem;
}
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #514fff;
    color: #ffffff;
    text-align: center;
    padding: 10px 0;
    font-size: 0.8rem;
    border-top: 1px solid #d1d5db;
}
/* Selectbox */
.stSelectbox {
    margin-bottom: 1rem;
}
.stSelectbox > div > div > div {
    border: 2px solid #3498db;
    border-radius: 5px;
}
/* File uploader */
.stFileUploader > div {
    border: 2px dashed #3498db;
    border-radius: 10px;
    padding: 2rem;
    text-align: center;
    transition: all 0.3s ease;
}
.stFileUploader > div:hover {
    background-color: #ffe224;
}
/* Buttons */
.stButton > button {
    background-color: #ffe224;
    color: rgb(0, 0, 0);
    border: none;
    border-radius: 5px;
    padding: 0.5rem 1rem;
    font-size: 1rem;
    font-weight: 600;
    text-transform: uppercase;
    transition: all 0.3s ease;
}
.stButton > button:hover {
    background-color: #2980b9;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
/* Success message */
.stSuccess {
    background-color: #2ecc71;
    color: white;
    padding: 1rem;
    border-radius: 5px;
    font-weight: 600;
}
/* Warning message */
.stWarning {
    background-color: #98620c;
    color: rgb(8, 6, 6);
    padding: 1rem;
    border-radius: 5px;
    font-weight: 600;
}
/* Error message */
.stError {
    background-color: #e74c3c;
    color: white;
    padding: 1rem;
    border-radius: 5px;
    font-weight: 600;
}
/* Info message */
.stInfo {
    background-color: #3498db;
    color: white;
    padding: 1rem;
    border-radius: 5px;
    font-weight: 600;
}
/* Image and PDF preview */
.stImage > img {
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
/* Responsive design */
@media (max-width: 768px) {
    .stApp header .stTitle {
        font-size: 2rem;
    }
    .stFileUploader > div {
        padding: 1rem;
    }
}
/* Custom header with logo */
.custom-header {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #2c3e50;
    padding: 1rem;
}
.custom-header img {
    height: 50px;
    margin-right: 1rem;
}
.custom-header h1 {
    color: r#2073f9;
    font-size: 2.5rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
}
</style>
""", unsafe_allow_html=True)


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
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, save_name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None


def remove_extension(file_path):
    return os.path.splitext(file_path)[0]


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
    return st.query_params.get("ticket_id", None)


# Document verification functions
def is_date_less_than_two_months(date_str):
    try:
        input_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    current_date = datetime.now()
    two_months_ago = current_date - relativedelta(months=2)

    if input_date > two_months_ago:
        return True
    else:
        return False


def is_difference_at_least_sixty_days(date1_str, date2_str):
    try:
        date1 = datetime.strptime(date1_str, "%Y-%m-%d")
        date2 = datetime.strptime(date2_str, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    difference = abs((date2 - date1).days)

    if difference >= 60:
        return True
    else:
        return False


def convert_to_jpg(file_path):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    def image_to_base64(image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    if ext == '.pdf':
        pdf_document = fitz.open(file_path)
        page = pdf_document.load_page(0)
        pix = page.get_pixmap()
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return image_to_base64(image)

    if ext in ['.png', '.jpeg', '.jpg']:
        image = Image.open(file_path)
        rgb_image = image.convert('RGB')
        return image_to_base64(rgb_image)


class Payslip(BaseModel):
    Verification: bool = Field(description="if Document Type is payslip return True")
    FirstName: str = Field(description="First Name in the name")
    LastName: str = Field(description="Last Name in the name")
    Date: str = Field(description="Date of the payslip")

    def has_empty_fields(self) -> bool:
        for field_name, field_value in self.__dict__.items():
            if field_value is None or (isinstance(field_value, str) and field_value.strip() == ""):
                return True
        return False


class BankStatement(BaseModel):
    Verification: bool = Field(description="Verification if document is a bank statement, True if it is")
    FirstName: str = Field(description="First Name in the name")
    LastName: str = Field(description="Last Name in the name")
    Firstdate: str = Field(description="date of the first transaction in the ledger in YYYY-MM-DD")
    Lastdate: str = Field(description="date of the last transaction in the ledger in YYYY-MM-DD")

    def has_empty_fields(self) -> bool:
        for field_name, field_value in self.__dict__.items():
            if field_value is None or (isinstance(field_value, str) and field_value.strip() == ""):
                return True
        return False


class PassportOutput(BaseModel):
    verification: bool = Field(description="If the document is a Passport , Return True")
    first_name: str = Field(
        description="Extract First name in the name,Return string with value NULL if you cannot identify ")
    last_name: str = Field(
        description="Extract Last name from the name,Return string with value NULL if you cannot identify")
    expiry_date: str = Field(
        description="What is the Expiry Date of the Passport,Return string with value  NULL if you cannot identify")
    nationality: str = Field(
        description="What country does the passport belong to?,Return string with value NULL if you cannot identify")
    passport_number: str = Field(
        description="Find out the passport number,Return string with value NULL if you cannot identify")


class LicenseOutput(BaseModel):
    verification: bool = Field(description="If the document is a driving license, Return True")
    first_name: str = Field(
        description="Extract First name in the name. The first name corresponds to entry number 2 on the license,Return string with value NULL if you cannot identify ")
    last_name: str = Field(
        description="Extract Last name from the name. Entry number 1 on the license contains the surname. Pick the last name from the surname.Return string with value NULL if you cannot identify")
    expiry_date: str = Field(
        description="What is the Expiry Date of the License,Return string with value  NULL if you cannot identify")
    country: str = Field(
        description="What country does the driving license belong to? Find it on the header of the image, country should be mentioned. Return string with value NULL if you cannot identify")
    license_number: str = Field(
        description="Find out the license number,Return string with value NULL if you cannot identify")


model = ChatOpenAI(model="gpt-4o")


def checkpayslip(file_path):
    image_data = convert_to_jpg(file_path)
    message = HumanMessage(
        content=[
            {"type": "text",
             "text": "Verify if the document type is a payslip. Give me Verification as a boolean, First Name, Last Name and date as YYYY-MM-DD in the image. Make the output passable to Json output parser "},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ],
    )
    structured_model = model.with_structured_output(Payslip)
    response = structured_model.invoke([message])
    if response.Verification == False:
        return -1
    else:
        if response.has_empty_fields():
            return 0
        if is_date_less_than_two_months(response.Date):
            return 1
        else:
            return 0


def checkbankstatement(file_path):
    loader = PyPDFLoader(file_path)
    pages = loader.load_and_split()
    text = " ".join(list(map(lambda page: page.page_content, pages)))
    structured_model = model.with_structured_output(BankStatement)
    response = structured_model.invoke(text)
    if response.Verification == False:
        return -1
    else:
        if response.has_empty_fields():
            return 0
        return 1 if is_difference_at_least_sixty_days(response.Firstdate, response.Lastdate) else 0


def passport_verify(image_path, first_name, last_name):
    image_data = convert_to_jpg(image_path)
    structured_model = model.with_structured_output(PassportOutput)
    message = HumanMessage(
        content=[
            {"type": "text",
             "text": "Verify whether the following document is a passport. Give me Verification as a boolean, First Name, Last Name and date as YYYY-MM-DD in the image. Make the output passable to Json Output Parser"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ],
    )
    response = structured_model.invoke([message])

    if not response.verification:
        return -1

    if any(field.upper() == "NULL" for field in
           [response.first_name, response.last_name, response.expiry_date, response.nationality,
            response.passport_number]):
        return 0

    if response.first_name.lower() != first_name.lower() or response.last_name.lower() != last_name.lower():
        return 0

    if not is_date_less_than_two_months(response.expiry_date):
        return 0

    if response.nationality.lower() not in ['britain', 'uk', 'gbr', 'british', 'united kingdom']:
        return 0

    if len(response.passport_number) != 9 or not response.passport_number.isdigit():
        return 0

    return 1


def license_verify(image_path, first_name, last_name):
    image_data = convert_to_jpg(image_path)
    structured_model = model.with_structured_output(LicenseOutput)
    message = HumanMessage(
        content=[
            {"type": "text",
             "text": "Verify whether the following document is a driving license. Give me Verification as a boolean, First Name, Last Name and date as YYYY-MM-DD in the image. Make the output passable to Json Output Parser"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ],
    )
    response = structured_model.invoke([message])

    if not response.verification:
        return -1

    if any(field.upper() == "NULL" for field in
           [response.first_name, response.last_name, response.expiry_date, response.country, response.license_number]):
        return 0

    if response.first_name.lower() != first_name.lower() or response.last_name.lower() != last_name.lower():
        return 0

    if not is_date_less_than_two_months(response.expiry_date):
        return 0

    if response.country.lower() not in ['britain', 'uk', 'gbr', 'british', 'united kingdom']:
        return 0

    return 1


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


def main():
    col1, col2 = st.columns([1,8])
    with col2:
      st.title("Document Validator")
    with col1:
      st.image(
        "https://www.blenheimchalcot.com/wp-content/uploads/2022/01/OakbrookGroup_Landscape_OnLight_RGB.png",
        width=175)

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

    url_ticket_id = get_ticket_id_from_url()

    col1, col2, col3, col4 = st.columns([3, 1, 2, 1])
    with col4:
        st.markdown("")
    with col3:
        st.markdown("")
    with col1:
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
                return
        else:
            st.warning("Please enter a Ticket ID to proceed.")
            return

        if uploaded_doc is not None:
            file_type = uploaded_doc.type
            with col3:
                if file_type in ["image/jpeg", "image/jpg", "image/png"]:
                    st.text("Image Preview:")
                    image = Image.open(uploaded_doc)
                    st.image(image, caption="Uploaded Image", use_column_width=True)
                elif file_type == "application/pdf":
                    st.text("PDF Preview:")
                    try:
                        pdf_pages = convert_from_bytes(uploaded_doc.getvalue(), first_page=0, last_page=1)
                        if pdf_pages:
                            st.image(pdf_pages[0], caption="First page of PDF", use_column_width=True)

                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_doc.getvalue()))
                        num_pages = len(pdf_reader.pages)
                        st.write(f"Number of pages: {num_pages}")
                    except Exception as e:
                        st.error(f"Error processing PDF: {str(e)}")

            if uploaded_doc != st.session_state.last_uploaded_file:
                file_path = save_uploaded_file(
                    uploaded_doc, document_type, get_uuid(ticket_id)
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
