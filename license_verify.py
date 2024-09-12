from dotenv import load_dotenv
import os 
import openai

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, conlist
import base64
import os
import datetime
from dateutil.relativedelta import relativedelta



class LicenseOutput(BaseModel):
        verification: bool = Field(description="If the document is a driving license, Reutrn True")
        first_name: str = Field (description="Extract First name in the name. the first name is corresponds to entry number 2 on the license,Return string with value NULL if you cannot identify ")
        last_name : str = Field(description="Extract Last name from the name. Entry number 1 on the license contains the surname. Pick the last name from the surname.Return string with value NULL if you cannot identify")
        expiry_date : str = Field(description="What is the Expiry Date of the Passport,Return string with value  NULL if you cannot identify")
        country : str = Field(description="What country does the driving license belong to? find it on the header of the image , country should be mentioned . return string with value NULL if you cannot identify")
        license_number: str=Field(description="Find out the passport number,Return string with value NULL if you cannot identify")




def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')
  
def extract_values(image_data):
    
    model = ChatOpenAI(model="gpt-4o")
    structured_model=model.with_structured_output(LicenseOutput)
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Verify whther the following document is a driving license. Give me Verification as a boolean, First Name, Last Name and date as YYYY-MM-DD in the image. Make the output passable to Json Output Parser. THe dirving license template is as such Header : County Driving License 1. Surname, 2 . First name "},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ],
    )
    response = structured_model.invoke([message])
    #parser = JsonOutputParser(pydantic_object=PassportOutput)
    print(response)

    return response


def has_null_fields(license_output: LicenseOutput) -> bool:
    # Check if any of the relevant fields have the string value "NULL"
    
    
    
    fields_to_check = [
        license_output.first_name, 
        license_output.last_name, 
        license_output.expiry_date, 
        license_output.country, 
        
    ]
    return any(field.upper() == "NULL" for field in fields_to_check)

def name_verify(document,first_name, last_name):
        if ' ' in document.first_name:
         str1= document.first_name.split(' ')[0].lower()
        else:
         str1=document.first_name.lower()
        
        if ' ' in document.last_name:
            str2= document.last_name.split(' ')[0].lower() 
        else:
            str2=document.last_name.lower()
        #print("read from doc",str1,str2)
        #print("Mtached with",first_name,last_name)

        if str1==first_name.lower() and str2==last_name.lower():
            
            print("name verified")
            return True
        else:
            return False

    

def expiry_check(date_str):
    # Parse the input date string to a datetime object
    try:
        input_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."
 
    # Get the current date
    current_date = datetime.datetime.now()
    # Calculate the date 2 months ago from the current date
    two_months_ago = current_date - relativedelta(months=6)
 
    # Check if the input date is less than 2 months ago
    if input_date > two_months_ago:
        return True
    else:
        return False


def nationality_check(input_string):
    # Convert the string to lowercase
    input_string = input_string.lower()
    #print(input_string)
    
    # Check if any of the terms 'britain', 'uk', or 'gbr' are in the string
    if 'britain' in input_string or 'uk' in input_string or 'gbr' in input_string or 'british' in input_string or 'united kingdom' in input_string:
        return True
        print("Nationality Correct")
    else:
        return False
    
def license_number_check(input_string):
    # Check if the string has exactly 9 characters and all are digits
    if len(input_string) == 9 and input_string.isdigit():
        return True
    else:
        return False





def verify_and_match(document, first_name, last_name):
    # Check if verification is true
    if  document.verification==True:

     if has_null_fields(document)==False:
        print("ok")
           # Match the provided name with the dictionary values
        if name_verify(document,first_name,last_name)==True:
            print("ok")
            #Check if passport valid for the next 6 months
            if expiry_check(document.expiry_date) == True :
            #if expiry_check("2025-01-01")==True:    
                #TO verify if the passport if from the UK region
                if nationality_check(document.country)==True:
                    
                
                 #   if license_number_check(first_name, document.first_name,document.license_number)== True:
                
                            return 1
                
                #    else:
                 #       return 0
                
                else:
                    return 0
            
            else:
                 return 0
        
        else:
            return 0
     else:
         return 0
    else:
        return -1











    
def license_verify(image_path,first_name,last_name):
    
    image_data = encode_image(image_path)

    output_dict = extract_values(image_data)

    
    
    result = verify_and_match(output_dict,first_name,last_name)


    return result