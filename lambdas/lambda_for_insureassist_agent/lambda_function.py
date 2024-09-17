import boto3
import uuid
import time
import logging
import pprint
import json
import botocore
import os

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize the Bedrock agent runtime client
config = botocore.config.Config(
    read_timeout=900,
    connect_timeout=900,
    retries={"max_attempts": 0}
)
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', config=config)


def lambda_handler(event, context):
    try:
        if event['httpMethod'] == 'OPTIONS':
            # Handle preflight request
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "OPTIONS, POST, GET",
                    "Access-Control-Allow-Headers": "Content-Type"
                },
                "body": ""
            }
        # Construct response headers with CORS support
        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",  # Allow requests from any origin
            "Access-Control-Allow-Methods": "OPTIONS, POST, GET",  # Allow OPTIONS and POST methods
            "Access-Control-Allow-Headers": "Content-Type"  # Allow Content-Type header
        }
        
    
        # Extract the agentAliasId from the response
        # agent_id = '9GCAG6HJDZ'
        # agent_alias_id ='TSTALIASID'
        agent_id = os.environ['INSUREASSIST_AGENTID']
        agent_alias_id = 'TSTALIASID'

        # Create a random id for session initiator id
        # session_id = event.get('sessionId') or str(uuid.uuid1())
        
        # For ALB
        event_body = json.loads(event['body'])
        session_id = event_body.get('sessionId') or str(uuid.uuid1())

        enable_trace = False
        end_session = False

        # Pause to make sure agent alias is ready
        # time.sleep(30)

        # Invoke the agent API
        agent_response = bedrock_agent_runtime_client.invoke_agent(
            # inputText= event.get('inputText'),
            inputText= event_body.get('inputText'),
            agentId=agent_id,
            agentAliasId=agent_alias_id, 
            sessionId=session_id,
            enableTrace=enable_trace, 
            endSession=end_session
        )
        event_stream = agent_response['completion']
        for event in event_stream:
            if 'chunk' in event:
                print("in chunk....")
                data = event['chunk']['bytes']
                logger.info(f"Final answer ->\n{data.decode('utf8')}")
                agent_answer = data.decode('utf8')
                end_event_received = True
            elif 'trace' in event:
                print("in trace...")
                logger.info(json.dumps(event['trace'], indent=2))
            else:
                raise Exception("Unexpected event.", event)
        
        # Just because I am using the ALB
        return {
            "statusCode": 200,
            "statusDescription": "200 OK",
            "isBase64Encoded": False,
            "headers": headers,
            "body": json.dumps({
                'sessionId': agent_response['sessionId'],
                'agentAnswer': agent_answer
            }) 
        }
    except Exception as e:
        logger.error("An error occurred: {}".format(str(e)))

        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Internal Server Error"})
        }
    

