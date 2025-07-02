# Slack PDF Processor - Serverless Application

A serverless application that automatically processes PDF reports uploaded to Slack channels and sends them via email.

## 🏗️ Architecture

This application uses AWS Lambda, API Gateway, S3, and SES to create a seamless workflow for processing PDF files from Slack.

![Architecture Diagram](architecture_diagram.md)

## ⚡ Features

- **Automatic PDF Detection**: Monitors Slack channels for PDF uploads
- **Secure Download**: Downloads PDFs from Slack using authenticated API calls
- **Email Delivery**: Automatically emails PDF reports to configured recipients
- **Serverless Architecture**: Cost-effective, scalable, and maintenance-free
- **Security**: Validates Slack webhook signatures and uses secure AWS services

## 🚀 Quick Start

1. **Prerequisites**: AWS CLI, Node.js, Serverless Framework
2. **Setup**: Copy `.env.example` to `.env` and configure your credentials
3. **Deploy**: Run `./deploy.sh dev`
4. **Configure**: Set up Slack Event Subscriptions with the provided webhook URL

See [setup_guide.md](setup_guide.md) for detailed instructions.

## 📁 Project Structure

```
├── handler.py              # Main Lambda function code
├── serverless.yml          # Serverless Framework configuration
├── requirements.txt        # Python dependencies
├── deploy.sh               # Deployment script
├── setup_guide.md          # Detailed setup instructions
├── architecture_diagram.md # System architecture documentation
├── tests/                  # Unit tests
└── .env.example           # Environment variables template
```

## 🔧 Configuration

Required environment variables:
- `SLACK_BOT_TOKEN`: Your Slack bot token
- `SLACK_SIGNING_SECRET`: Slack app signing secret
- `EMAIL_FROM`: Verified sender email address
- `EMAIL_TO`: Recipient email address

## 📊 Monitoring

Monitor the application using:
```bash
npx serverless logs -f slackWebhook -t --stage dev
```

## 💰 Cost

Typical usage costs less than $1/month with AWS Free Tier.

## 🔒 Security

- Webhook signature validation
- IAM roles with minimal permissions
- Automatic file cleanup
- No public S3 access

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.