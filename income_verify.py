from dotenv import load_dotenv
import os 
import openai
from PIL import Image
import fitz
import base64
from io import BytesIO
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.pydantic_v1 import BaseModel, Field


load_dotenv('.env')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

def is_date_less_than_two_months(date_str):
    # Parse the input date string to a datetime object
    try:
        input_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    # Get the current date
    current_date = datetime.now()

    # Calculate the date 2 months ago from the current date
    two_months_ago = current_date - relativedelta(months=2)

    # Check if the input date is less than 2 months ago
    if input_date > two_months_ago:
        return True
    else:
        return False

def is_difference_at_least_sixty_days(date1_str, date2_str):
    # Parse the input date strings to datetime objects
    try:
        date1 = datetime.strptime(date1_str, "%Y-%m-%d")
        date2 = datetime.strptime(date2_str, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    # Calculate the difference in days
    difference = abs((date2 - date1).days)

    # Check if the difference is at least 60 days
    if difference >= 60:
        return True
    else:
        return False
    
model = ChatOpenAI(model="gpt-4o")

def convert_to_jpg(file_path):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    def image_to_base64(image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    # Convert PDF to JPG and return base64 encoding of the first page
    if ext == '.pdf':
        pdf_document = fitz.open(file_path)
        page = pdf_document.load_page(0)  # Load the first page
        pix = page.get_pixmap()
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return image_to_base64(image)

    # Convert PNG or JPEG to JPG and return base64 encoding
    if ext in ['.png', '.jpeg', '.jpg']:
        image = Image.open(file_path)
        rgb_image = image.convert('RGB')
        return image_to_base64(rgb_image)
    
class Payslip(BaseModel):
    Verification: bool = Field(description="if Document Type is payslip return True")
    FirstName: str = Field(description="First Name in the name")
    LastName: str = Field(description="Last Name in the name")
    Date: str = Field(description= "Date of the payslip")

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
    Lastdate : str = Field(description="date of the last transaction in the ledger in YYYY-MM-DD")

    def has_empty_fields(self) -> bool:
        for field_name, field_value in self.__dict__.items():
            if field_value is None or (isinstance(field_value, str) and field_value.strip() == ""):
                return True
        return False

def checkpayslip(file_path) :
    image_data = convert_to_jpg(file_path)
    message = HumanMessage(
    content=[
        {"type": "text", "text": "Verify if the document type is a payslip. Give me Verification as a boolean, First Name, Last Name and date as YYYY-MM-DD in the image. Make the output passable to Json output parser "},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
        },
        ],
    )
    structured_model = model.with_structured_output(Payslip)
    response = structured_model.invoke([message])
    if response.Verification == False :
        return -1
    else :

        if response.has_empty_fields() :
            return 0
        
        #logic for comparing given first and last name to db
        if is_date_less_than_two_months(response.Date) :
            return 1
        else :
            return 0

def checkbankstatement(file_path) :
    loader = PyPDFLoader(file_path)
    pages = loader.load_and_split()
    text = " ".join(list(map(lambda page: page.page_content, pages)))
    structured_model = model.with_structured_output(BankStatement)
    response = structured_model.invoke(text)
    if response.Verification == False :
        return "Incorrect Document Uploaded"
    else :
        
        if response.has_empty_fields() :
            return "reupload better image"
        
        #logic for comparing given first and last name to db
        return is_difference_at_least_sixty_days(response.Firstdate, response.Lastdate)
