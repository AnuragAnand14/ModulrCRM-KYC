import openai
import base64
import datetime
from dateutil.relativedelta import relativedelta
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# Define your Pydantic model
class LicenseOutput(BaseModel):
    verification: bool = Field(description="If the document is a driving license, Return True")
    first_name: str = Field(description="Extract First name in the name. the first name is corresponds to entry number 2 on the license, Return string with value NULL if you cannot identify ")
    last_name: str = Field(description="Extract Last name from the name. Entry number 1 on the license contains the surname. Pick the last name from the surname. Return string with value NULL if you cannot identify")
    expiry_date: str = Field(description="What is the Expiry Date of the Passport, Return string with value NULL if you cannot identify")
    country: str = Field(description="What country does the driving license belong to? Find it on the header of the image, country should be mentioned. Return string with value NULL if you cannot identify")
    license_number: str = Field(description="Find out the passport number. Return string with value NULL if you cannot identify")

# Fetch OpenAI API key from Streamlit secrets
def get_openai_api_key():
    import streamlit as st
    return st.secrets["openai"]["api_key"]

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
  
def extract_values(image_data):
    # Fetch API key from Streamlit secrets
    api_key = get_openai_api_key()
    openai.api_key = api_key

    model = ChatOpenAI(model="gpt-4o")
    structured_model = model.with_structured_output(LicenseOutput)
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Verify whether the following document is a driving license. Give me Verification as a boolean, First Name, Last Name and date as YYYY-MM-DD in the image. Make the output passable to Json Output Parser. The driving license template is as such Header: County Driving License 1. Surname, 2. First name "},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ],
    )
    response = structured_model.invoke([message])
    print(response)

    return response

def has_null_fields(license_output: LicenseOutput) -> bool:
    fields_to_check = [
        license_output.first_name, 
        license_output.last_name, 
        license_output.expiry_date, 
        license_output.country, 
    ]
    return any(field.upper() == "NULL" for field in fields_to_check)

def name_verify(document, first_name, last_name):
    str1 = document.first_name.split(' ')[0].lower() if ' ' in document.first_name else document.first_name.lower()
    str2 = document.last_name.split(' ')[0].lower() if ' ' in document.last_name else document.last_name.lower()

    if str1 == first_name.lower() and str2 == last_name.lower():
        print("name verified")
        return True
    else:
        return False

def expiry_check(date_str):
    try:
        input_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."
 
    current_date = datetime.datetime.now()
    two_months_ago = current_date - relativedelta(months=6)
 
    return input_date > two_months_ago

def nationality_check(input_string):
    input_string = input_string.lower()
    return 'britain' in input_string or 'uk' in input_string or 'gbr' in input_string or 'british' in input_string or 'united kingdom' in input_string

def license_number_check(input_string):
    return len(input_string) == 9 and input_string.isdigit()

def verify_and_match(document, first_name, last_name):
    if document.verification:
        if not has_null_fields(document):
            if name_verify(document, first_name, last_name):
                if expiry_check(document.expiry_date):
                    if nationality_check(document.country):
                        return 1
                return 0
            return 0
        return 0
    return -1

def license_verify(image_path, first_name, last_name):
    image_data = encode_image(image_path)
    output_dict = extract_values(image_data)
    result = verify_and_match(output_dict, first_name, last_name)
    return result
