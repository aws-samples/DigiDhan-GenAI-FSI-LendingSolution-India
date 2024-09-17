import json
import base64
import re
import boto3
import os

# Create an S3 client
s3 = boto3.client('s3')
ssm = boto3.client('ssm')

image_bucket_name = os.environ['IMAGE_BUCKET_SUBMITTED_BY_UI']
html_bucket_name = os.environ['HTML_BUCKET_NAME']
apialb_dns_name = os.environ['INSURE_ASSIST_API_ALB_DNS_NAME']

# Preload ALB DNS name during initialization
uialb_dns_name = None

try:
    response = ssm.get_parameter(
        Name='/insureassist/ui_alb_dns_name',
        WithDecryption=False
    )
    uialb_dns_name = response['Parameter']['Value'].lower()
    print("Preloaded UI ALB DNS Name:", uialb_dns_name)
except Exception as e:
    print("Error preloading UI ALB DNS name:", e)


def get_image_extension(image_data):
    if image_data.startswith(b'\xFF\xD8'):
        return 'jpg'
    elif image_data.startswith(b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'):
        return 'png'
    elif image_data.startswith(b'\x47\x49\x46\x38\x37\x61') or image_data.startswith(b'\x47\x49\x46\x38\x39\x61'):
        return 'gif'
    else:
        return None  # Unknown file format


def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    print("UI ALB ::", uialb_dns_name)

    # Handle preflight request
    if event['httpMethod'] == 'OPTIONS':
        print("Handling preflight request")
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": f"http://{uialb_dns_name}",
                "Access-Control-Allow-Methods": "OPTIONS, POST, GET",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }

    # Construct response headers with CORS support
    headers = {
        "Content-Type": "text/html",
        "Access-Control-Allow-Origin": f"http://{uialb_dns_name}",
        "Access-Control-Allow-Methods": "OPTIONS, POST, GET",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    print("Headers is ::", headers)

    # Check if the request contains a body
    if 'body' in event and event['body']:
        print("Request contains body")
        if event.get('isBase64Encoded') == True:
            print("Body is base64 encoded")
            # Decode the base64-encoded body
            decoded_body = base64.b64decode(event['body'])
            print("Decoded body:", decoded_body)

            # Get the content type from the headers
            content_type_str = event['headers'].get('content-type')
            print("Content type:", content_type_str)

            if content_type_str:
                # Convert to bytes
                content_type_bytes = content_type_str.encode("utf-8")
                boundary_match = re.search(b'boundary=(.*)', content_type_bytes)
                print("Boundary match:", boundary_match)
                if boundary_match:
                    boundary = boundary_match.group(1)
                    print("Boundary:", boundary)
                    # Split the body into parts based on the boundary
                    parts = decoded_body.split(b'--' + boundary)
                    for i, part in enumerate(parts):
                        print(f"Part {i}:", part)
                        print("=" * 50)
                        # Skip empty parts
                        if not part.strip():
                            continue

                        # Extract headers and data from each part
                        headers_and_data = part.split(b'\r\n\r\n', 1)
                        if len(headers_and_data) == 2:
                            headers, data = headers_and_data
                        else:
                            print("Invalid part structure:", headers_and_data)
                            continue

                        # Process the headers to get filename and content type
                        content_type_match = re.search(b'Content-Type: (.*)', headers)
                        filename_match = re.search(b'filename="(.*)"', headers)
                        if content_type_match and filename_match:
                            content_type = content_type_match.group(1).decode("utf-8")
                            filename = filename_match.group(1).decode("utf-8")
                            print("Content type:", content_type)
                            print("Filename:", filename)

                            # Check if the part contains image data
                            if content_type.startswith('image'):
                                print("Part contains image data")
                                # Get the image extension
                                image_extension = get_image_extension(data)
                                print("Image extension:", image_extension)
                                if image_extension:
                                    # Generate a unique filename for the image
                                    image_key = f"{filename}"
                                    print("Image key:", image_key)

                                    try:
                                        # Upload the image to S3 bucket
                                        s3.put_object(Body=data, Bucket=image_bucket_name, Key=image_key)
                                        print("Image uploaded successfully to S3")

                                        # Construct the S3 URL
                                        # s3_url = f"https://your-s3-bucket-name.s3.amazonaws.com/{image_key}"
                                        s3_url = f"{image_key}"
                                        print("S3 URL:", s3_url)

                                        # Return success response with S3 URL
                                        return {
                                            "statusCode": 200,
                                            "headers": {
                                                "Content-Type": "application/json",
                                                "Access-Control-Allow-Origin": f"http://{uialb_dns_name}",
                                                "Access-Control-Allow-Methods": "OPTIONS, POST, GET",
                                                "Access-Control-Allow-Headers": "Content-Type"
                                            },
                                            "body": json.dumps(
                                                {'message': 'Image uploaded successfully.', 's3_url': s3_url,
                                                 'image_path': image_key})
                                        }
                                    except Exception as e:
                                        # Return error response if upload fails
                                        print("Error uploading image to S3:", e)
                                        return {
                                            "statusCode": 500,
                                            "headers": {
                                                "Content-Type": "application/json",
                                                "Access-Control-Allow-Origin": f"http://{uialb_dns_name}",
                                                "Access-Control-Allow-Methods": "OPTIONS, POST, GET",
                                                "Access-Control-Allow-Headers": "Content-Type"
                                            },
                                            "body": json.dumps({'error': str(e)})
                                        }
                            else:
                                print("Not an image part:", filename)
                        else:
                            print("Missing headers or filename")
            else:
                print("Content type not found in headers")

    # # Read the HTML file
    # with open('index.html', 'r') as file:
    #     html_content = file.read()

    # Serve index.html from S3
    try:
        response = s3.get_object(Bucket=html_bucket_name, Key='index.html')
        html_content = response['Body'].read().decode('utf-8')
        # Replace placeholders in the HTML content
        html_content = html_content.replace('http://uiAlbforinsureassist/', f"http://{uialb_dns_name}/")
        html_content = html_content.replace('http://insureAssistApi/', f"http://{apialb_dns_name}/")
        # html_content = html_content.replace('human_face.png', f"https://media.istockphoto.com/id/1300845620/vector/user-icon-flat-isolated-on-white-background-user-symbol-vector-illustration.jpg?s=1024x1024&w=is&k=20&c=-mUWsTSENkugJ3qs5covpaj-bhYpxXY-v9RDpzsw504=")
        # html_content = html_content.replace('robot_face.jpg', f"https://media.istockphoto.com/id/2078304100/vector/chatbots.jpg?s=1024x1024&w=is&k=20&c=LTKZpcqnvEBgvFCzdgMXmm1SzzFKQs8i21aREa_AEg8=")

    except Exception as e:
        html_content = f"<h1>Error: {e}</h1>"

    # Construct the HTTP response
    return {
        "statusCode": 200,
        "statusDescription": "200 OK",
        "isBase64Encoded": False,
        "headers": headers,
        "body": html_content
    }
