"""Simplified FastAPI application with CSV storage."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import pandas as pd
from datetime import datetime

from app.classifier.rules_engine import RulesClassifier
from app.storage.csv_storage import CSVStorage

# Initialize FastAPI app
app = FastAPI(
    title="Embassy Aviation Mailbot - Simple Version",
    description="Email triage automation with CSV storage",
    version="1.0.0"
)

# Initialize storage and classifier
storage = CSVStorage()
classifier = RulesClassifier()

# Pydantic models
class EmailRequest(BaseModel):
    subject: str
    body: str
    sender: str
    message_id: Optional[str] = None

class ProcessingResult(BaseModel):
    email_id: str
    ticket_id: str
    category: str
    priority: str
    is_aog: bool
    aircraft_registration: Optional[str] = None
    confidence: float

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard."""
    
    # Get summary statistics
    summary = storage.generate_summary_report()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Embassy Aviation Mailbot Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; color: #2c3e50; margin-bottom: 30px; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
            .stat-card {{ background: #ecf0f1; padding: 20px; border-radius: 8px; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #3498db; }}
            .stat-label {{ color: #7f8c8d; margin-top: 5px; }}
            .aog-stat {{ background: #e74c3c; color: white; }}
            .section {{ margin: 30px 0; }}
            .section h3 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            .api-endpoint {{ background: #2c3e50; color: white; padding: 10px; border-radius: 5px; font-family: monospace; margin: 10px 0; }}
            .category-list {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
            .category-item {{ background: #3498db; color: white; padding: 10px; border-radius: 5px; text-align: center; }}
            .btn {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #2980b9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚁 Embassy Aviation Mailbot</h1>
                <p>Email Triage Automation System - Dashboard</p>
                <p><strong>Status:</strong> ✅ OPERATIONAL | <strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{summary['total_emails']}</div>
                    <div class="stat-label">Total Emails Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{summary['total_tickets']}</div>
                    <div class="stat-label">Tickets Created</div>
                </div>
                <div class="stat-card aog-stat">
                    <div class="stat-number">{summary['aog_count']}</div>
                    <div class="stat-label">AOG Emergencies</div>
                </div>
            </div>
            
            <div class="section">
                <h3>📊 Email Categories Processed</h3>
                <div class="category-list">
                    {_generate_category_cards(summary['categories'])}
                </div>
            </div>
            
            <div class="section">
                <h3>🚀 Quick Actions</h3>
                <a href="/process-sample" class="btn">Process Sample Emails</a>
                <a href="/reports/csv" class="btn">Download CSV Report</a>
                <a href="/reports/dashboard-data" class="btn">View Raw Data</a>
                <a href="/docs" class="btn">API Documentation</a>
            </div>
            
            <div class="section">
                <h3>📡 API Endpoints</h3>
                <div class="api-endpoint">POST /process-email - Process a single email</div>
                <div class="api-endpoint">GET /reports/summary - Get processing summary</div>
                <div class="api-endpoint">GET /reports/csv - Download CSV report</div>
                <div class="api-endpoint">GET /health - System health check</div>
            </div>
            
            <div class="section">
                <h3>ℹ️ System Information</h3>
                <p><strong>Storage:</strong> CSV Files (data/)</p>
                <p><strong>Classification:</strong> Aviation-specific AI rules</p>
                <p><strong>Features:</strong> AOG detection, Aircraft registration extraction, Priority assignment</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def _generate_category_cards(categories: Dict) -> str:
    """Generate HTML for category cards."""
    if not categories:
        return '<div class="category-item">No data yet</div>'
    
    cards = []
    for category, count in categories.items():
        cards.append(f'<div class="category-item">{category}<br><strong>{count}</strong></div>')
    
    return ''.join(cards)

@app.post("/process-email", response_model=ProcessingResult)
async def process_email(email: EmailRequest):
    """Process a single email through the triage system."""
    
    try:
        # Generate message ID if not provided
        message_id = email.message_id or f"msg-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Save email to CSV
        email_data = {
            'message_id': message_id,
            'subject': email.subject,
            'sender': email.sender,
            'body_text': email.body
        }
        email_id = storage.save_email(email_data)
        
        # Classify email
        classification = classifier.classify_email(email.subject, email.body, email.sender)
        
        # Create ticket
        ticket_number = f"EMB-{datetime.now().strftime('%Y%m%d')}-{len(storage.get_tickets_df()) + 1:03d}"
        ticket_data = {
            'ticket_number': ticket_number,
            'title': email.subject,
            'category': classification.category.value,
            'priority': classification.priority.value,
            'status': 'new',
            'customer_email': email.sender,
            'aircraft_registration': classification.aircraft_registration,
            'is_aog': classification.is_aog
        }
        ticket_id = storage.save_ticket(ticket_data)
        
        # Log activity
        activity_data = {
            'ticket_id': ticket_id,
            'activity_type': 'email_processed',
            'title': f'Email classified as {classification.category.value}',
            'description': f'Subject: {email.subject}',
            'actor_type': 'system'
        }
        storage.save_activity(activity_data)
        
        return ProcessingResult(
            email_id=email_id,
            ticket_id=ticket_id,
            category=classification.category.value,
            priority=classification.priority.value,
            is_aog=classification.is_aog,
            aircraft_registration=classification.aircraft_registration,
            confidence=classification.confidence
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/process-sample")
async def process_sample_emails():
    """Process sample aviation emails for demonstration."""
    
    sample_emails = [
        {
            "subject": "URGENT AOG - Aircraft N789XY grounded at JFK",
            "body": "Aircraft N789XY is grounded due to engine failure. Immediate maintenance assistance required.",
            "sender": "ops@airline.com"
        },
        {
            "subject": "Scheduled maintenance request N123AB", 
            "body": "Please schedule 100-hour inspection for aircraft N123AB at LAX facility.",
            "sender": "maintenance@airline.com"
        },
        {
            "subject": "Invoice inquiry #INV-12345",
            "body": "I have questions about the charges on invoice #INV-12345 for recent maintenance work.",
            "sender": "billing@airline.com"
        },
        {
            "subject": "Parts delivery confirmation N456CD",
            "body": "Confirming delivery of hydraulic components for aircraft N456CD scheduled maintenance.",
            "sender": "parts@supplier.com"
        },
        {
            "subject": "EMERGENCY - N999EF hydraulic system failure",
            "body": "Aircraft N999EF experiencing complete hydraulic system failure at ORD. Need immediate support.",
            "sender": "emergency@airline.com"
        }
    ]
    
    results = []
    for email_data in sample_emails:
        email_request = EmailRequest(**email_data)
        result = await process_email(email_request)
        results.append(result)
    
    return {
        "message": f"Processed {len(results)} sample emails",
        "results": results,
        "summary": storage.generate_summary_report()
    }

@app.get("/reports/summary")
async def get_summary_report():
    """Get processing summary report."""
    return storage.generate_summary_report()

@app.get("/reports/csv")
async def download_csv_report():
    """Download comprehensive CSV report."""
    
    # Generate comprehensive report
    emails_df = storage.get_emails_df()
    tickets_df = storage.get_tickets_df()
    
    # Create report file
    report_file = "data/embassy_aviation_report.csv"
    
    if not tickets_df.empty:
        # Add processing statistics
        tickets_df['report_generated'] = datetime.now().isoformat()
        tickets_df.to_csv(report_file, index=False)
    else:
        # Create empty report
        pd.DataFrame({
            'message': ['No data processed yet'],
            'report_generated': [datetime.now().isoformat()]
        }).to_csv(report_file, index=False)
    
    return FileResponse(
        path=report_file,
        media_type='text/csv',
        filename=f"embassy_aviation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

@app.get("/reports/dashboard-data")
async def get_dashboard_data():
    """Get all data for dashboard view."""
    
    return {
        "emails": storage.get_emails_df().to_dict('records') if not storage.get_emails_df().empty else [],
        "tickets": storage.get_tickets_df().to_dict('records') if not storage.get_tickets_df().empty else [],
        "activities": storage.get_activities_df().to_dict('records') if not storage.get_activities_df().empty else [],
        "summary": storage.generate_summary_report()
    }

@app.get("/health")
async def health_check():
    """System health check."""
    
    return {
        "status": "healthy",
        "system": "Embassy Aviation Mailbot",
        "version": "1.0.0",
        "storage": "CSV Files",
        "timestamp": datetime.now().isoformat(),
        "data_files": {
            "emails": os.path.exists("data/emails.csv"),
            "tickets": os.path.exists("data/tickets.csv"),
            "activities": os.path.exists("data/activities.csv")
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)