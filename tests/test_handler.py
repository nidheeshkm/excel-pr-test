import json
import time
import pytest
import boto3
from moto import mock_s3, mock_ses
from unittest.mock import patch, MagicMock
import os
import sys

# Add the parent directory to sys.path to import handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import handler


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'SLACK_BOT_TOKEN': 'xoxb-test-token',
        'SLACK_SIGNING_SECRET': 'test-signing-secret',
        'EMAIL_FROM': 'test@example.com',
        'EMAIL_TO': 'recipient@example.com',
        'S3_BUCKET': 'test-bucket'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def sample_slack_event():
    """Sample Slack event for testing."""
    return {
        'headers': {
            'x-slack-signature': 'v0=test-signature',
            'x-slack-request-timestamp': str(int(time.time()))
        },
        'body': json.dumps({
            'type': 'event_callback',
            'event': {
                'type': 'file_shared',
                'file_id': 'F1234567890'
            }
        })
    }


@pytest.fixture
def sample_file_info():
    """Sample file info for testing."""
    return {
        'id': 'F1234567890',
        'name': 'test-report.pdf',
        'mimetype': 'application/pdf',
        'size': 1024,
        'url_private_download': 'https://files.slack.com/test-file.pdf'
    }


@mock_s3
def test_store_pdf_in_s3(mock_env_vars, sample_file_info):
    """Test storing PDF in S3."""
    # Create mock S3 bucket
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket=mock_env_vars['S3_BUCKET'])
    
    # Test storing PDF
    pdf_content = b'fake pdf content'
    s3_key = handler.store_pdf_in_s3(pdf_content, sample_file_info)
    
    assert s3_key is not None
    assert s3_key.endswith('test-report.pdf')
    
    # Verify file was stored
    response = s3.get_object(Bucket=mock_env_vars['S3_BUCKET'], Key=s3_key)
    assert response['Body'].read() == pdf_content


def test_verify_slack_signature_invalid_timestamp(mock_env_vars):
    """Test Slack signature verification with invalid timestamp."""
    import time
    
    event = {
        'headers': {
            'x-slack-signature': 'v0=test-signature',
            'x-slack-request-timestamp': str(int(time.time()) - 400)  # 400 seconds ago
        },
        'body': 'test-body'
    }
    
    result = handler.verify_slack_signature(event)
    assert result is False


@patch('handler.requests.get')
def test_download_pdf_from_slack(mock_get, mock_env_vars, sample_file_info):
    """Test downloading PDF from Slack."""
    # Mock successful response
    mock_response = MagicMock()
    mock_response.content = b'fake pdf content'
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    result = handler.download_pdf_from_slack(sample_file_info)
    
    assert result == b'fake pdf content'
    mock_get.assert_called_once()


@patch('handler.requests.get')
def test_download_pdf_from_slack_failure(mock_get, mock_env_vars, sample_file_info):
    """Test PDF download failure."""
    # Mock failed response
    mock_get.side_effect = Exception("Network error")
    
    result = handler.download_pdf_from_slack(sample_file_info)
    
    assert result is None


@mock_s3
@mock_ses
def test_send_pdf_email(mock_env_vars, sample_file_info):
    """Test sending PDF email."""
    # Setup mock S3
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket=mock_env_vars['S3_BUCKET'])
    
    # Store test PDF
    pdf_content = b'fake pdf content'
    s3_key = 'test-pdf.pdf'
    s3.put_object(
        Bucket=mock_env_vars['S3_BUCKET'],
        Key=s3_key,
        Body=pdf_content,
        ContentType='application/pdf'
    )
    
    # Setup mock SES
    ses = boto3.client('ses', region_name='us-east-1')
    ses.verify_email_identity(EmailAddress=mock_env_vars['EMAIL_FROM'])
    
    # Test sending email
    message_info = {'user': 'U123456', 'channel': 'C123456'}
    result = handler.send_pdf_email(s3_key, sample_file_info, message_info)
    
    assert result is True


def test_health_check():
    """Test health check endpoint."""
    result = handler.health_check({}, {})
    
    assert result['statusCode'] == 200
    body = json.loads(result['body'])
    assert body['status'] == 'healthy'
    assert 'timestamp' in body


@patch('handler.verify_slack_signature')
def test_slack_webhook_url_verification(mock_verify, mock_env_vars):
    """Test Slack URL verification challenge."""
    mock_verify.return_value = True
    
    event = {
        'headers': {},
        'body': json.dumps({
            'type': 'url_verification',
            'challenge': 'test-challenge-123'
        })
    }
    
    result = handler.slack_webhook(event, {})
    
    assert result['statusCode'] == 200
    assert result['body'] == 'test-challenge-123'


@patch('handler.verify_slack_signature')
def test_slack_webhook_unauthorized(mock_verify, mock_env_vars):
    """Test unauthorized webhook request."""
    mock_verify.return_value = False
    
    event = {
        'headers': {},
        'body': json.dumps({'type': 'test'})
    }
    
    result = handler.slack_webhook(event, {})
    
    assert result['statusCode'] == 401
    body = json.loads(result['body'])
    assert body['error'] == 'Unauthorized'


if __name__ == '__main__':
    pytest.main([__file__])