"""Twilio SMS connector for sending SMS alerts."""

from typing import Optional
from datetime import datetime

from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TwilioSMSConnector:
    """Twilio SMS connector for sending SMS alerts."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_FROM_NUMBER
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not configured")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None
    ) -> Optional[str]:
        """Send SMS message."""
        if not self.client:
            logger.error("Twilio client not initialized")
            return None
        
        if not self._validate_phone_number(to_number):
            logger.error("Invalid phone number format", phone=to_number)
            return None
        
        from_num = from_number or self.from_number
        
        try:
            message_obj = self.client.messages.create(
                body=message[:1600],  # SMS limit with buffer
                from_=from_num,
                to=to_number
            )
            
            logger.info(
                "SMS sent successfully",
                to_number=self._mask_phone_number(to_number),
                message_sid=message_obj.sid,
                message_length=len(message)
            )
            
            return message_obj.sid
            
        except TwilioException as e:
            logger.error(
                "Twilio error sending SMS",
                to_number=self._mask_phone_number(to_number),
                error_code=getattr(e, 'code', None),
                error=str(e)
            )
            return None
        except Exception as e:
            logger.error(
                "Unexpected error sending SMS",
                to_number=self._mask_phone_number(to_number),
                error=str(e)
            )
            return None
    
    async def send_escalation_sms(
        self,
        to_number: str,
        ticket_number: str,
        customer_email: str,
        category: str,
        priority: str,
        escalation_level: int
    ) -> Optional[str]:
        """Send escalation SMS alert."""
        urgency = "🔴 URGENT" if priority.lower() == "critical" else "🟡 HIGH" if priority.lower() == "high" else "🟢 NORMAL"
        
        message = (
            f"{urgency} Embassy Aviation Alert\n"
            f"Ticket #{ticket_number}\n"
            f"Category: {category}\n"
            f"Customer: {customer_email}\n"
            f"Escalation Level: {escalation_level}\n"
            f"Action required - please check email and respond to customer."
        )
        
        if priority.lower() == "critical":
            message += "\n⚠️ AOG SITUATION - IMMEDIATE ATTENTION REQUIRED"
        
        return await self.send_sms(to_number, message)
    
    async def send_aog_alert(
        self,
        to_numbers: list[str],
        ticket_number: str,
        customer_email: str,
        aircraft_registration: Optional[str],
        location: Optional[str]
    ) -> list[Optional[str]]:
        """Send critical AOG alert to multiple numbers."""
        aircraft_info = f" - {aircraft_registration}" if aircraft_registration else ""
        location_info = f" at {location}" if location else ""
        
        message = (
            f"🚨 AIRCRAFT ON GROUND ALERT 🚨\n"
            f"Ticket #{ticket_number}\n"
            f"Aircraft{aircraft_info}{location_info}\n"
            f"Customer: {customer_email}\n"
            f"IMMEDIATE RESPONSE REQUIRED\n"
            f"Check email for full details"
        )
        
        results = []
        for number in to_numbers:
            result = await self.send_sms(number, message)
            results.append(result)
        
        return results
    
    async def send_acknowledgment_reminder(
        self,
        to_number: str,
        ticket_number: str,
        minutes_since_escalation: int
    ) -> Optional[str]:
        """Send reminder SMS about unacknowledged ticket."""
        message = (
            f"Embassy Aviation Reminder\n"
            f"Ticket #{ticket_number} still needs attention\n"
            f"Escalated {minutes_since_escalation} minutes ago\n"
            f"Please acknowledge to stop alerts"
        )
        
        return await self.send_sms(to_number, message)
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Basic phone number validation."""
        import re
        
        # Remove common formatting
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Basic validation: +country code + 7-15 digits
        if not cleaned:
            return False
        
        # Must start with + or digit
        if not (cleaned.startswith('+') or cleaned[0].isdigit()):
            return False
        
        # Remove + for length check
        digits = cleaned.lstrip('+')
        
        # Must be 7-15 digits
        if not (7 <= len(digits) <= 15):
            return False
        
        return True
    
    def _mask_phone_number(self, phone: str) -> str:
        """Mask phone number for logging."""
        if len(phone) <= 4:
            return phone
        
        return phone[:2] + "*" * max(0, len(phone) - 4) + phone[-2:]
    
    async def check_connection(self) -> bool:
        """Check Twilio connection by validating credentials."""
        if not self.client:
            logger.error("Twilio client not initialized")
            return False
        
        try:
            # Try to fetch account info to validate credentials
            account = self.client.api.accounts(self.account_sid).fetch()
            
            logger.info(
                "Twilio connection test successful",
                account_sid=account.sid,
                status=account.status
            )
            return True
            
        except TwilioException as e:
            logger.error(
                "Twilio connection test failed",
                error_code=getattr(e, 'code', None),
                error=str(e)
            )
            return False
        except Exception as e:
            logger.error("Unexpected error testing Twilio connection", error=str(e))
            return False
    
    async def get_message_status(self, message_sid: str) -> Optional[dict]:
        """Get status of sent message."""
        if not self.client:
            return None
        
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                "sid": message.sid,
                "status": message.status,
                "to": message.to,
                "from": message.from_,
                "date_sent": message.date_sent,
                "error_code": message.error_code,
                "error_message": message.error_message
            }
            
        except TwilioException as e:
            logger.error(
                "Error fetching message status",
                message_sid=message_sid,
                error=str(e)
            )
            return None