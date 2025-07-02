# Slack PDF Processor - Setup Guide

This guide will walk you through setting up the serverless application that processes PDF reports from Slack and sends them via email.

## Prerequisites

1. **AWS Account** with CLI configured
2. **Slack App** with appropriate permissions
3. **Node.js** (v18 or later)
4. **Serverless Framework** installed globally

## Step 1: AWS Setup

### 1.1 Configure AWS CLI
```bash
aws configure
```

### 1.2 Verify SES Email Address
```bash
# Replace with your email address
aws ses verify-email-identity --email-address your-email@example.com
```
Check your email and click the verification link.

## Step 2: Slack App Setup

### 2.1 Create Slack App
1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name your app (e.g., "PDF Processor")
4. Select your workspace

### 2.2 Configure OAuth & Permissions
1. Go to "OAuth & Permissions"
2. Add the following Bot Token Scopes:
   - `files:read`
   - `channels:history` (if monitoring channels)
   - `chat:write` (optional, for confirmations)

### 2.3 Install App to Workspace
1. Click "Install to Workspace"
2. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### 2.4 Get Signing Secret
1. Go to "Basic Information"
2. Copy the "Signing Secret"

## Step 3: Environment Configuration

### 3.1 Create Environment File
```bash
cp .env.example .env
```

### 3.2 Fill in Environment Variables
Edit `.env` with your actual values:
```bash
SLACK_BOT_TOKEN=xoxb-your-actual-token-here
SLACK_SIGNING_SECRET=your-actual-signing-secret-here
EMAIL_FROM=your-verified-email@example.com
EMAIL_TO=recipient@example.com
```

### 3.3 Source Environment
```bash
source .env
```

## Step 4: Deploy Application

### 4.1 Install Dependencies
```bash
npm install
```

### 4.2 Deploy to AWS
```bash
# Deploy to development stage
./deploy.sh dev

# Or deploy to production
./deploy.sh prod
```

The script will output the API Gateway URL you'll need for Slack configuration.

## Step 5: Configure Slack Event Subscriptions

### 5.1 Enable Event Subscriptions
1. In your Slack app settings, go to "Event Subscriptions"
2. Toggle "Enable Events" to ON
3. Set Request URL to the API Gateway URL from deployment output
4. Example: `https://abcd1234.execute-api.us-east-1.amazonaws.com/dev/slack/events`

### 5.2 Subscribe to Bot Events
Add these events:
- `file_shared` - When files are shared
- `message.channels` - When messages are posted (includes file uploads)

### 5.3 Save Changes
Click "Save Changes" at the bottom

## Step 6: Testing

### 6.1 Upload Test PDF
1. Go to your Slack workspace
2. Upload a PDF file to any channel where the bot is present
3. Check CloudWatch logs for processing status

### 6.2 Monitor Logs
```bash
npx serverless logs -f slackWebhook -t --stage dev
```

### 6.3 Check Email
You should receive an email with the PDF attachment within a few minutes.

## Troubleshooting

### Common Issues

#### 1. Email Not Sending
- Verify your email address in AWS SES
- Check IAM permissions for SES
- Ensure you're in a region where SES is available

#### 2. Slack Events Not Received
- Verify the webhook URL is correct
- Check that signing secret matches
- Ensure bot has necessary permissions

#### 3. PDF Download Fails
- Verify bot token has `files:read` permission
- Check that the bot is in the channel where file was shared

#### 4. Lambda Timeout
- Increase timeout in `serverless.yml`
- Check PDF file size (Lambda has memory/time limits)

### Debugging Commands

```bash
# Check function logs
npx serverless logs -f slackWebhook --stage dev

# Invoke function locally
npx serverless invoke -f slackWebhook --data '{"test": true}'

# Check AWS resources
aws lambda list-functions --query 'Functions[?contains(FunctionName, `slack-pdf`)]'
```

## Cost Considerations

This serverless application uses the following AWS services:
- **Lambda**: Pay per execution (very low cost for occasional use)
- **API Gateway**: Pay per request
- **S3**: Storage cost (files are auto-deleted after 1 day)
- **SES**: Pay per email sent

For typical usage (a few PDFs per day), the cost should be under $1/month.

## Security Notes

- Webhook signatures are validated to ensure requests come from Slack
- S3 bucket has public access blocked
- IAM roles follow principle of least privilege
- Files are automatically cleaned up from S3
- Environment variables store sensitive data

## Customization

### Adding Email Templates
Edit the `send_pdf_email` function in `handler.py` to customize email format.

### Processing Multiple File Types
Modify the file type check in `process_pdf_file` to handle other formats.

### Adding Notification Channels
Integrate with other services like SNS for additional notifications.

## Support

For issues or questions:
1. Check the logs using the debugging commands above
2. Review the architecture diagram for understanding the flow
3. Ensure all prerequisites are met