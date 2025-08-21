"""SMTP email connector for sending outbound emails."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import List, Optional
from datetime import datetime

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SMTPEmailConnector:
    """SMTP connector for sending emails."""
    
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USER
        self.password = settings.SMTP_PASS
        self.from_email = settings.SMTP_FROM
        self.from_name = settings.SMTP_FROM_NAME
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def send_email(
        self,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        is_html: bool = False,
        reply_to: Optional[str] = None
    ) -> bool:
        """Send an email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart("alternative") if is_html else MIMEText(body, "plain", "utf-8")
            
            if isinstance(msg, MIMEMultipart):
                # Add both text and HTML parts for better compatibility
                text_part = MIMEText(self._html_to_text(body), "plain", "utf-8")
                html_part = MIMEText(body, "html", "utf-8")
                msg.attach(text_part)
                msg.attach(html_part)
            
            # Set headers
            msg["Subject"] = subject
            msg["From"] = formataddr((self.from_name, self.from_email))
            msg["To"] = ", ".join(to_recipients)
            
            if cc_recipients:
                msg["Cc"] = ", ".join(cc_recipients)
            
            if reply_to:
                msg["Reply-To"] = reply_to
            
            # Add custom headers for tracking
            msg["X-Mailer"] = "Embassy Aviation Mailbot"
            msg["X-Priority"] = "1"  # High priority for service requests
            
            # All recipients for sending
            all_recipients = to_recipients.copy()
            if cc_recipients:
                all_recipients.extend(cc_recipients)
            if bcc_recipients:
                all_recipients.extend(bcc_recipients)
            
            # Send email
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                
                text = msg.as_string()
                server.sendmail(self.from_email, all_recipients, text)
            
            logger.info(
                "Email sent successfully",
                to_count=len(to_recipients),
                cc_count=len(cc_recipients) if cc_recipients else 0,
                subject=subject[:50]
            )
            return True
            
        except smtplib.SMTPException as e:
            logger.error(
                "SMTP error sending email",
                to_recipients=to_recipients,
                subject=subject,
                error=str(e)
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error sending email",
                to_recipients=to_recipients,
                subject=subject,
                error=str(e)
            )
            return False
    
    async def send_confirmation_email(
        self,
        customer_email: str,
        customer_name: Optional[str],
        ticket_number: str,
        subject: str,
        category: str,
        priority: str
    ) -> bool:
        """Send confirmation email to customer."""
        greeting = f"Dear {customer_name}," if customer_name else "Dear Customer,"
        
        # Determine response time based on priority
        if priority.lower() == "critical":
            response_time = "within 15 minutes"
        elif priority.lower() == "high":
            response_time = "within 1 hour"
        else:
            response_time = "within 4 hours"
        
        body = f"""
{greeting}

Thank you for contacting Embassy Aviation. We have received your {category.lower()} request and have created ticket #{ticket_number} for tracking purposes.

Request Details:
- Ticket Number: {ticket_number}
- Category: {category.title()}
- Priority: {priority.title()}
- Subject: {subject}
- Expected Response Time: {response_time}

Our team will review your request and respond {response_time}. If this is an Aircraft on Ground (AOG) emergency, please also call our 24/7 hotline at +1-XXX-XXX-XXXX.

For future reference, you can use ticket number #{ticket_number} when following up on this request.

Thank you for choosing Embassy Aviation.

Best regards,
Embassy Aviation Customer Service Team

---
This is an automated message. Please do not reply to this email.
If you need immediate assistance, please contact our support team directly.
        """.strip()
        
        confirmation_subject = f"[Embassy Aviation] Request Received - Ticket #{ticket_number}"
        
        return await self.send_email(
            to_recipients=[customer_email],
            subject=confirmation_subject,
            body=body,
            is_html=False
        )
    
    async def send_escalation_email(
        self,
        to_recipients: List[str],
        ticket_number: str,
        customer_email: str,
        subject: str,
        category: str,
        priority: str,
        escalation_level: int,
        original_message: str
    ) -> bool:
        """Send escalation email to internal team."""
        urgency_text = "🔴 URGENT" if priority.lower() == "critical" else "🟡 HIGH PRIORITY" if priority.lower() == "high" else "🟢 NORMAL"
        
        body = f"""
{urgency_text} - Service Request Escalation (Level {escalation_level})

Ticket Details:
- Ticket Number: {ticket_number}
- Customer: {customer_email}
- Category: {category.title()}
- Priority: {priority.title()}
- Escalation Level: {escalation_level}
- Original Subject: {subject}

Original Customer Message:
{'-' * 50}
{original_message[:1000]}{'...' if len(original_message) > 1000 else ''}
{'-' * 50}

Action Required:
Please review this {category.lower()} request and respond to the customer as soon as possible. 

{'⚠️  This is an Aircraft on Ground (AOG) situation requiring immediate attention!' if priority.lower() == 'critical' else ''}

To stop this escalation, please reply to this email or update the ticket status in our system.

Quick Actions:
- Reply to customer: {customer_email}
- View ticket details: [Ticket System Link]
- Mark as acknowledged: [Acknowledgment Link]

Embassy Aviation Operations Team
        """.strip()
        
        escalation_subject = f"[Embassy Aviation] {urgency_text} Escalation #{ticket_number} - {subject[:50]}"
        
        return await self.send_email(
            to_recipients=to_recipients,
            subject=escalation_subject,
            body=body,
            is_html=False,
            reply_to=customer_email
        )
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text (basic implementation)."""
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        
        # Replace common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text
    
    async def check_connection(self) -> bool:
        """Check SMTP connection."""
        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                logger.info("SMTP connection test successful")
                return True
        except Exception as e:
            logger.error("SMTP connection test failed", error=str(e))
            return False