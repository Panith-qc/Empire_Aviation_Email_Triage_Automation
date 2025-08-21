# Project Summary
The Embassy Aviation Mailbot is an AI-driven email automation system designed for Empire Aviation USA. This project automates the processing of aviation-related service requests, enhancing communication efficiency and response times through email and SMS notifications. By integrating with various email accounts (Gmail, Outlook, IMAP), the Mailbot improves operational safety and reduces costs associated with aviation inquiries.

# Project Module Description
The system consists of several functional modules:
- **Email Monitoring Service**: Monitors multiple inboxes for new service requests.
- **Service Request Detection**: Identifies and categorizes incoming requests.
- **Auto-Reply System**: Confirms receipt of requests to customers with ticket numbers.
- **Internal Escalation**: Sends notifications to the internal team via email and SMS.
- **Smart Email Routing**: Routes requests to appropriate team members based on location.
- **Escalation Management**: Stops escalation once a response is received.
- **Activity Logging**: Logs all activities for monthly reporting.
- **Reporting Service**: Generates CSV reports detailing email processing statistics.
- **Web Dashboard**: Provides a user interface for real-time email processing and report generation.

# Directory Tree
```
fastapi_template/
├── app/                             # Main application code
│   ├── simple_main.py               # FastAPI application entry point
│   ├── classifier/                   # AI classification engine
│   │   ├── rules_engine.py           # Classification rules
│   │   ├── rules.yaml                # Configuration rules
│   │   └── ml_classifier.py          # Machine learning classifier
│   └── storage/                      # Data storage layer
│       └── csv_storage.py            # CSV file operations
├── aviation_data/                   # Directory for generated CSV reports
├── real_email_data/                 # Outputs from real email processing
├── quick_test_data/                 # Outputs from quick tests
├── quick_email_test.py              # Testing script for sample aviation emails
├── email_inbox_processor.py          # Processes real aviation emails from inboxes
├── standalone_demo.py                # Self-contained demo processor
├── run_simple.py                     # Launches the web dashboard
├── ARCHITECTURE_DOCUMENT.md          # System architecture documentation
├── email_setup_guide.md             # Instructions for setting up email providers
├── SIMPLE_DEPLOYMENT_GUIDE.md       # Deployment instructions
├── Empire_Aviation_USA_Project_Status_Update.md # Project status update
├── Empire_Aviation_Project_Tracking.csv # Project tracking file
├── Empire_Aviation_USA_Status_Dashboard.pdf # Professional dashboard report
└── Empire_Aviation_USA_Status_Dashboard.html # HTML version of the dashboard
└── simple_requirements.txt           # Minimal dependencies
```

# File Description Inventory
- **app/simple_main.py**: Entry point for the FastAPI application.
- **app/classifier/**: Contains the AI classification engine and associated rules.
- **app/storage/csv_storage.py**: Implements CSV-based storage for emails and tickets.
- **email_inbox_processor.py**: Monitors and processes real aviation emails from inboxes.
- **quick_email_test.py**: A self-contained script for testing the classification engine.
- **ARCHITECTURE_DOCUMENT.md**: Comprehensive documentation of the system architecture and business requirements.
- **email_setup_guide.md**: Instructions for configuring email providers.
- **SIMPLE_DEPLOYMENT_GUIDE.md**: Instructions for deploying the application.
- **Empire_Aviation_USA_Project_Status_Update.md**: Detailed project status update document.
- **Empire_Aviation_Project_Tracking.csv**: CSV file for tracking project tasks and status.
- **Empire_Aviation_USA_Status_Dashboard.pdf**: Executive presentation of project status.
- **Empire_Aviation_USA_Status_Dashboard.html**: HTML version of the project status dashboard.

# Technology Stack
- **Languages**: Python 3.8+
- **Frameworks**: FastAPI
- **Data Handling**: Built-in CSV module for data management
- **Testing**: pytest (if applicable)

# Usage
### Installation
1. Install Python requirements:
   ```bash
   pip install -r simple_requirements.txt
   ```

### Running the System
- To process real aviation emails, run:
   ```bash
   python email_inbox_processor.py
   ```
   Follow the prompts to enter your email settings.

- For testing with sample emails, run:
   ```bash
   python quick_email_test.py
   ```

- To launch the web dashboard, run:
   ```bash
   python run_simple.py
   ```

### Viewing Results
The system generates CSV files in the `real_email_data/` directory:
- `real_emails_[date].csv` for complete email data.
- `real_tickets_[date].csv` for ticket tracking information.
- `real_summary_[date].csv` for statistics.
