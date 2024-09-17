import json
import os
import logging
import random
import string
import boto3
import uuid
import time
import pprint
import json
import botocore
import io
from PIL import Image
import base64

logger = logging.getLogger()
logger.setLevel(logging.INFO)

existing_customer = ['KZ9ENJ2GIP', 'KZ9ENJ2G1P']


def send_approval_emails(pan, customer_name, loan_id, creditScore, loan_amt):
    html_string = create_html_string_approved(pan, customer_name, loan_id, creditScore, loan_amt)
    message = f"Hi {customer_name} Your loan request ID: {loan_id} has been created, Our loan officer has been notied of you application. We will notify you once the application status changes"
    subject = f"Loan Request Created - {loan_id}"
    ses_client = boto3.client('ses')
    CHARSET = "UTF-8"
    recepients = ["reenacs@amazon.com", "shshaill@amazon.com"]
    response = ses_client.send_email(
        Destination={
            'ToAddresses': recepients,
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': CHARSET,
                    'Data': html_string,
                }
            },
            'Subject': {
                'Charset': CHARSET,
                'Data': subject,
            },
        },
        Source=f"Loan Approval Alert<reenacs@amazon.com>"
    )
    return message


def create_html_string_approved(pan, customerName, loanId, creditScore, loanAmt):
    html_string = '''
        <html>
        <head>
        <style>
        table {
          border-collapse: collapse;
          width: 100%;
        }

        th, td {
          padding: 8px;
          text-align: left;
          border-bottom: 1px solid #DDD;
        }

        tr:hover {background-color: #D6EEEE;}
        </style>
        </head>
        <body>

        <h2>Loan Application Details</h2>
        <p> Hi {customerName}, your loan has been sanctioned </p>

        <table>
          <tr>
            <th bgcolor="#5dabba" >Details</th>
            <th bgcolor="#5dabba"> Value</th>
          </tr>
          <tr>
            <td>Customer Name</td>
            <td>{customerName}</td>
          </tr>
          <tr>
            <td>Application Id</td>
            <td>{loanId}</td>
          </tr>
          <tr>
            <td>Pan Number</td>
            <td>{pan}</td>
          </tr>
          <tr>
            <td>Credit Score</td>
            <td>{creditScore}</td>
          </tr>
          <tr>
            <td>Sanctioned Loan Amount</td>
            <td>{loanAmt}</td>
          </tr>
        </table>
        </body>
        </html>
        '''
    html_string = html_string.replace('{pan}', pan).replace('{customerName}', customerName).replace('{loanId}',
                                                                                                    loanId).replace(
        '{creditScore}', creditScore).replace('{loanAmt}', loanAmt)
    return html_string


def bedrock_reader(lines, entities, image_bytes):
    bedrock_client = boto3.client("bedrock-runtime")
    system_prompt = "You are Document Extractor tool, which will read Images content, and return data into Json format."
    prompt = f"""
    You are Document Extractor Tool, you will be dealing with Indian Legal Documents. You need to analyse document Images and return a Json data as output.
    Here are the lines found in the image : {lines}  
    Here are the entities in the image: {entities}
    Documents could be (Any Indian Legal Document):
    - Aadhar card
    - PAN Card

    Make sure of following:
    - No other content should be there apart from output json.
    - Document could be in any Indian Language but your output should have data in English only.
    - First key of json should be DocumentType, in this you can mention type of document, Supported values for DocumentType are AADHAR, PAN, OTHERS
    - Now in 2rd key of Json should be DocumentExtraction, and here you can put information related to the document. If Document is PAN, then Mandatory fields are IsPan, customerName, pan, dob. If document is AADHAR then mandatory fields are IsAadhar, Name, dob, Sex, aadhar, and Address 
    - Make sure you are following this structure strictly. 

    """

    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "system": system_prompt,
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": encoded_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
    )

    response = bedrock_client.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=body,
        accept="application/json",
        contentType="application/json"
    )
    response_body = response.get('body').read().decode('utf-8')
    response_json = json.loads(response_body)
    content_text = response_json['content'][0]['text']
    return json.loads(content_text)


def process_text_detection(bucket, document):
    s3_connection = boto3.resource("s3")
    client = boto3.client("textract")
    s3_object = s3_connection.Object(bucket, document)
    s3_response = s3_object.get()
    stream = io.BytesIO(s3_response['Body'].read())
    image = Image.open(stream)
    response = client.detect_document_text(Document={'S3Object': {'Bucket': bucket, 'Name': document}})
    blocks = response['Blocks']
    line_list = []
    for block in blocks:
        if block["BlockType"] == "LINE":
            line_list.append(block["Text"])
    return line_list


def entity_detection(lines):
    response_entities = []
    comprehend = boto3.client(service_name='comprehend')
    for line in lines:
        entities_list = []
        found_entities = comprehend.detect_entities(Text=line, LanguageCode='en')
        for response_data, values in found_entities.items():
            for item in values:
                if "Text" in item:
                    print("Entities found:")
                    for text, val in item.items():
                        if text == "Text":
                            entities_list.append(val)
                            print(val)
        response_entities.append(entities_list)
    return response_entities


def verify_proof(bucket, document):
    response = {}
    s3_client = boto3.client('s3')
    lines = process_text_detection(bucket, document)
    response_ents = entity_detection(lines)
    response = s3_client.get_object(Bucket=bucket, Key=document)
    obj = response['Body'].read()
    extracted_field = bedrock_reader(lines, response_ents, obj)
    return extracted_field


# Function to check whether user is an existing customer
def check_exiting_user(pan):
    is_exiting_user = False
    if pan in existing_customer:
        is_exiting_user = True
        # riskscore = random.randrange(50,250)
        # creditscore = random.randrange(600,750)
    if is_exiting_user:
        logger.info("User is an existing Customer")
    else:
        logger.info("User is a new Customer")
    return is_exiting_user


# Function to create a loan application
def create_loan(customer_name, loan_amt, pan, creditScore):
    loan_id = 'CLM' + str(random.randint(10000, 99999))  # Generating a random claim ID as an example

    risk_score = float(creditScore)
    if risk_score > 610:
        approved_amount = int(loan_amt) * 1.0
        acknowledgment_message = f"Hi {customer_name} Your loan request ID: {loan_id} has been approved, we will shortly sanctuned an amount of {approved_amount}. "
        send_approval_emails(pan, customer_name, loan_id, creditScore, loan_amt )
    else:
        acknowledgment_message = f"Hi {customer_name}  We regret to inform that the loan was not sanctioned. Never the less, we would like to see you in the future, happy banking."

    return {"loanid": loan_id, "status": acknowledgment_message}


def calc_riskScore(pan, aadhar):
    if pan in ['GNV8XFWZS0', 'GNY8XFWZS0']:
        risk_score = 150
        creditScore = 710
    else:
        risk_score = random.randint(200, 210)
        creditScore = random.randint(400, 600)
    return creditScore, risk_score


def custom_message(Is_old_user):
    if Is_old_user:
        message = "Hi , I see that you are an existing user. Please upload your PAN card image to proceed further."
    else:
        message = "User is a new Customer. Please upload your PAN card image to proceed further."

    return message


def lambda_handler(event, context):

    api_path = event['apiPath']
    logger.info('API Path')
    logger.info(api_path)
    logger.info('Lambda Event Request:')
    logger.info(json.dumps(event))

    if api_path == 'POST__CreateLoan__DetermineUserDetails':
        print(event['requestBody']['content']['application/json']['properties'])
        data = {
            "customerName": "",
            "pan": "",
            "emailAddress": "",
            "loanAmt": ""
        }
        # Extracting claim details from the parsed JSON
        print(event['requestBody']['content']['application/json']['properties'])
        for claim_request in event['requestBody']['content']['application/json']['properties']:
            if claim_request['type'] == 'string':
                data[claim_request['name']] = claim_request['value']
            else:
                data[claim_request['name']] = json.loads(claim_request['value'])
        pan = data['pan']
        is_user= check_exiting_user(pan)
        body = {"isExistingUser": is_user,
                "pan": pan,
                "customerName": data['customerName'],
                "emailAddress": data['emailAddress'],
                "loanAmt": data['loanAmt']
                }

    elif api_path == 'GET__CreateLoan__GreetUser':
        print(event['requestBody']['content']['application/json']['properties'])
        data = {
            "isExistingUser": ""
        }
        # Extracting claim details from the parsed JSON
        print(event['requestBody']['content']['application/json']['properties'])
        for claim_request in event['requestBody']['content']['application/json']['properties']:
            if claim_request['type'] == 'string':
                data[claim_request['name']] = claim_request['value']
            else:
                data[claim_request['name']] = json.loads(claim_request['value'])

        message = custom_message(data['isExistingUser'])
        body = {"isExistingUser": data['isExistingUser'],
                "customerMessage": message
                }

    elif api_path == 'POST__CreateLoan__VerifyUserPanCard':
        print(event['requestBody']['content']['application/json']['properties'])
        data = {
            "isExistingUser": "",
            "image_path": ""}
        # Extracting damage details from the parsed JSON
        print(event['requestBody']['content']['application/json']['properties'])
        for damage_detail in event['requestBody']['content']['application/json']['properties']:
            if damage_detail['type'] == 'string':
                data[damage_detail['name']] = damage_detail['value']
            else:
                data[damage_detail['name']] = json.loads(damage_detail['value'])
        isExistingUser = data['isExistingUser']
        image_path = data['image_path']
        s3_object_key = image_path
        s3_bucket = os.environ['PROOF_IMAGE_SUBMITTED_BUCKET']
        try:
            data = verify_proof(s3_bucket, s3_object_key)
            if isExistingUser:
                riskscore = random.randrange(50, 250)
                creditscore = random.randrange(620, 750)
                print("Risk Score: " + str(riskscore))
                print("Credit Score: " + str(creditscore))
                body = {"isPan": data['DocumentExtraction']['IsPan'],
                        "customerName": data['DocumentExtraction']['customerName'],
                        "pan": data['DocumentExtraction']['pan'],
                        "dob": data['DocumentExtraction']['dob'],
                        "isExistingUser": isExistingUser,
                        "riskScore": riskscore,
                        "creditScore": creditscore}
            else:
                body = {"isPan": data['DocumentExtraction']['IsPan'],
                        "customerName": data['DocumentExtraction']['customerName'],
                        "pan": data['DocumentExtraction']['pan'],
                        "dob": data['DocumentExtraction']['dob'],
                        "isExistingUser": isExistingUser}
        except Exception as e:
            body = {"message": "Request the user to upload the image"}

    elif api_path == 'POST__CreateLoan__VerifyUserAadharCard':
        print(event['requestBody']['content']['application/json']['properties'])
        data = {
            "isExistingUser": "",
            "image_path": "",
            "isPan": "",
            "customerName": "",
            "dob": "",
            "pan": "",
        }
        # Extracting damage details from the parsed JSON
        print(event['requestBody']['content']['application/json']['properties'])
        for damage_detail in event['requestBody']['content']['application/json']['properties']:
            if damage_detail['type'] == 'string':
                data[damage_detail['name']] = damage_detail['value']
            else:
                data[damage_detail['name']] = json.loads(damage_detail['value'])
        image_path = data['image_path']
        s3_bucket = os.environ['PROOF_IMAGE_SUBMITTED_BUCKET']
        try:
            res = verify_proof(s3_bucket, image_path)
            creditScore, riskScore = calc_riskScore(data['pan'], res['DocumentExtraction']['aadhar'])
            body = {"isAadhar": res['DocumentExtraction']['IsAadhar'],
                    "isPan": data['isPan'],
                    "pan": data['pan'],
                    "customerName": data['customerName'],
                    "dob": data['dob'],
                    "sex": res['DocumentExtraction']['Sex'],
                    "address": res['DocumentExtraction']['Address'],
                    "aadhar": res['DocumentExtraction']['aadhar'],
                    "riskScore": riskScore,
                    "creditScore": creditScore,
                    "isExistingUser": data['isExistingUser']}
        except Exception as e:
            body = {"message": "Request the user to upload the image"}

    elif api_path == 'POST__CreateLoan__SubmitLoanApplication':

        data = {
            "pan": "",
            "customerName": "",
            "address": "",
            "loanAmt": "",
            "riskScore": "",
            "creditScore": ""
        }
        # Extracting claim details from the parsed JSON
        print(event['requestBody']['content']['application/json']['properties'])
        for claim_request in event['requestBody']['content']['application/json']['properties']:
            if claim_request['type'] == 'string':
                data[claim_request['name']] = claim_request['value']
            else:
                data[claim_request['name']] = json.loads(claim_request['value'])
        customer_name = data['customerName']
        address = data['address']
        loan_amt = data['loanAmt']
        pan = data['pan']
        risk_score = data['riskScore']
        creditScore = data['creditScore']
        body = create_loan(customer_name, loan_amt, pan, creditScore)

    else:
        body = {"message": "{} is not a valid API. Please try another one.".format(api_path)}

    response_body = {
        'application/json': {
            'body': json.dumps(body)
        }
    }

    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }

    api_response = {
        'messageVersion': '1.0',
        'response': action_response
    }

    return api_response
