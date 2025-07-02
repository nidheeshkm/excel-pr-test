import json
import os
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, Optional
import boto3
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from botocore.exceptions import ClientError

# Setup logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

# Initialize Slack client
slack_client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))

# Configuration
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
S3_BUCKET = os.getenv('S3_BUCKET')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = os.getenv('EMAIL_TO')


def verify_slack_signature(event: Dict[str, Any]) -> bool:
    """Verify that the request is from Slack using the signing secret."""
    try:
        slack_signature = event['headers'].get('x-slack-signature', '')
        slack_timestamp = event['headers'].get('x-slack-request-timestamp', '')
        
        # Check if timestamp is recent (within 5 minutes)
        if abs(time.time() - int(slack_timestamp)) > 60 * 5:
            logger.warning("Request timestamp too old")
            return False
        
        # Create signature
        sig_basestring = f"v0:{slack_timestamp}:{event['body']}"
        my_signature = 'v0=' + hmac.new(
            SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(my_signature, slack_signature)
    except Exception as e:
        logger.error(f"Error verifying Slack signature: {str(e)}")
        return False


def slack_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle incoming Slack webhook events."""
    try:
        logger.info(f"Received webhook event: {json.dumps(event)}")
        
        # Verify Slack signature
        if not verify_slack_signature(event):
            logger.error("Invalid Slack signature")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        # Parse the request body
        body = json.loads(event['body'])
        
        # Handle URL verification challenge
        if body.get('type') == 'url_verification':
            return {
                'statusCode': 200,
                'body': body['challenge']
            }
        
        # Handle file upload events
        if body.get('type') == 'event_callback':
            event_data = body.get('event', {})
            
            if event_data.get('type') == 'file_shared':
                # Process the file asynchronously
                process_file_event(event_data)
            
            elif event_data.get('type') == 'message' and event_data.get('files'):
                # Handle direct file uploads in messages
                for file_info in event_data['files']:
                    if file_info.get('mimetype') == 'application/pdf':
                        process_pdf_file(file_info, event_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'success'})
        }
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }


def process_slack_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Slack events that contain PDF files."""
    try:
        logger.info(f"Processing Slack event: {json.dumps(event)}")
        
        file_info = event.get('file_info')
        message_info = event.get('message_info', {})
        
        if not file_info:
            logger.error("No file info provided")
            return {'statusCode': 400, 'body': 'No file info'}
        
        # Download PDF from Slack
        pdf_content = download_pdf_from_slack(file_info)
        if not pdf_content:
            logger.error("Failed to download PDF")
            return {'statusCode': 500, 'body': 'Download failed'}
        
        # Store PDF in S3
        s3_key = store_pdf_in_s3(pdf_content, file_info)
        if not s3_key:
            logger.error("Failed to store PDF in S3")
            return {'statusCode': 500, 'body': 'Storage failed'}
        
        # Send email with PDF
        success = send_pdf_email(s3_key, file_info, message_info)
        
        # Clean up S3 file
        cleanup_s3_file(s3_key)
        
        if success:
            return {'statusCode': 200, 'body': 'Email sent successfully'}
        else:
            return {'statusCode': 500, 'body': 'Email sending failed'}
            
    except Exception as e:
        logger.error(f"Error processing Slack event: {str(e)}")
        return {'statusCode': 500, 'body': 'Processing failed'}


def process_file_event(event_data: Dict[str, Any]) -> None:
    """Process file shared events from Slack."""
    try:
        file_id = event_data.get('file_id')
        if not file_id:
            logger.warning("No file ID in event")
            return
        
        # Get file info from Slack API
        response = slack_client.files_info(file=file_id)
        file_info = response['file']
        
        if file_info.get('mimetype') == 'application/pdf':
            process_pdf_file(file_info, event_data)
            
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
    except Exception as e:
        logger.error(f"Error processing file event: {str(e)}")


def process_pdf_file(file_info: Dict[str, Any], message_info: Dict[str, Any]) -> None:
    """Process a PDF file from Slack."""
    try:
        logger.info(f"Processing PDF file: {file_info.get('name', 'unknown')}")
        
        # Invoke the processing function asynchronously
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=f"{os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'slack-pdf-processor-dev-processSlackEvent')}",
            InvocationType='Event',  # Asynchronous
            Payload=json.dumps({
                'file_info': file_info,
                'message_info': message_info
            })
        )
        
    except Exception as e:
        logger.error(f"Error invoking processing function: {str(e)}")


def download_pdf_from_slack(file_info: Dict[str, Any]) -> Optional[bytes]:
    """Download PDF file from Slack."""
    try:
        file_url = file_info.get('url_private_download')
        if not file_url:
            logger.error("No download URL available")
            return None
        
        headers = {
            'Authorization': f'Bearer {os.getenv("SLACK_BOT_TOKEN")}'
        }
        
        response = requests.get(file_url, headers=headers, timeout=60)
        response.raise_for_status()
        
        logger.info(f"Downloaded PDF: {len(response.content)} bytes")
        return response.content
        
    except requests.RequestException as e:
        logger.error(f"Error downloading PDF: {str(e)}")
        return None


def store_pdf_in_s3(pdf_content: bytes, file_info: Dict[str, Any]) -> Optional[str]:
    """Store PDF content in S3 bucket."""
    try:
        file_name = file_info.get('name', 'unknown.pdf')
        timestamp = int(time.time())
        s3_key = f"pdfs/{timestamp}_{file_name}"
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=pdf_content,
            ContentType='application/pdf'
        )
        
        logger.info(f"Stored PDF in S3: {s3_key}")
        return s3_key
        
    except ClientError as e:
        logger.error(f"Error storing PDF in S3: {str(e)}")
        return None


def send_pdf_email(s3_key: str, file_info: Dict[str, Any], message_info: Dict[str, Any]) -> bool:
    """Send email with PDF attachment."""
    try:
        # Get PDF from S3
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        pdf_content = response['Body'].read()
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = f"PDF Report from Slack: {file_info.get('name', 'Unknown')}"
        
        # Email body
        body_text = f"""
        A new PDF report has been shared in Slack.
        
        File Details:
        - Name: {file_info.get('name', 'Unknown')}
        - Size: {file_info.get('size', 0)} bytes
        - Uploaded by: {message_info.get('user', 'Unknown user')}
        - Channel: {message_info.get('channel', 'Unknown channel')}
        - Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
        
        Please find the PDF report attached.
        
        Best regards,
        Slack PDF Processor
        """
        
        msg.attach(MIMEText(body_text, 'plain'))
        
        # Attach PDF
        pdf_attachment = MIMEApplication(pdf_content, _subtype='pdf')
        pdf_attachment.add_header(
            'Content-Disposition',
            'attachment',
            filename=file_info.get('name', 'report.pdf')
        )
        msg.attach(pdf_attachment)
        
        # Send email using SES
        response = ses_client.send_raw_email(
            Source=EMAIL_FROM,
            Destinations=[EMAIL_TO],
            RawMessage={'Data': msg.as_string()}
        )
        
        logger.info(f"Email sent successfully: {response['MessageId']}")
        return True
        
    except ClientError as e:
        logger.error(f"Error sending email: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {str(e)}")
        return False


def cleanup_s3_file(s3_key: str) -> None:
    """Clean up temporary PDF file from S3."""
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"Cleaned up S3 file: {s3_key}")
    except ClientError as e:
        logger.warning(f"Error cleaning up S3 file {s3_key}: {str(e)}")


# Health check function
def health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Simple health check endpoint."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'healthy',
            'timestamp': time.time(),
            'version': '1.0.0'
        })
    }