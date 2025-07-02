#!/bin/bash

# Deployment script for Slack PDF Processor Serverless App

set -e

echo "🚀 Starting deployment of Slack PDF Processor..."

# Check if required environment variables are set
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_SIGNING_SECRET" ] || [ -z "$EMAIL_FROM" ] || [ -z "$EMAIL_TO" ]; then
    echo "❌ Error: Required environment variables are not set."
    echo "Please set the following environment variables:"
    echo "  - SLACK_BOT_TOKEN"
    echo "  - SLACK_SIGNING_SECRET"
    echo "  - EMAIL_FROM"
    echo "  - EMAIL_TO"
    echo ""
    echo "You can copy .env.example to .env and fill in the values, then source it:"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your values"
    echo "  source .env"
    exit 1
fi

# Set default stage if not provided
STAGE=${1:-dev}

echo "📦 Installing Node.js dependencies..."
npm install

echo "🔧 Configuring AWS credentials (if needed)..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

echo "📧 Checking SES email verification status..."
aws ses get-identity-verification-attributes --identities "$EMAIL_FROM" > /dev/null 2>&1 || {
    echo "⚠️  Warning: Email address $EMAIL_FROM may not be verified in SES."
    echo "Please verify your email address in AWS SES console."
    echo "You can continue deployment, but emails won't be sent until verified."
}

echo "🏗️  Deploying to stage: $STAGE..."
npx serverless deploy --stage "$STAGE"

# Get the deployed API Gateway URL
API_URL=$(npx serverless info --stage "$STAGE" --verbose | grep -i "post.*slack/events" | awk '{print $NF}')

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Configuration Summary:"
echo "  Stage: $STAGE"
echo "  API Gateway URL: $API_URL"
echo "  S3 Bucket: slack-pdf-processor-$STAGE-slack-pdf-processor"
echo ""
echo "🔧 Next Steps:"
echo "1. Configure Slack App Event Subscriptions:"
echo "   - Go to your Slack app settings"
echo "   - Navigate to Event Subscriptions"
echo "   - Enable events and set Request URL to: $API_URL"
echo "   - Subscribe to bot events: file_shared, message.channels"
echo ""
echo "2. Verify your email address in AWS SES if not already done"
echo ""
echo "3. Test by uploading a PDF file to your Slack channel"
echo ""
echo "📊 Monitor logs with: npx serverless logs -f slackWebhook -t --stage $STAGE"