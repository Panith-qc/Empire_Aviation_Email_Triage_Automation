"""Microsoft Graph API connector for email operations."""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import httpx
import msal
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.email import EmailMessage, EmailAttachment
from app.utils.logging import get_logger
from app.utils.validation import sanitize_input, clean_subject_line

logger = get_logger(__name__)


class GraphEmailConnector:
    """Microsoft Graph API connector for email operations."""
    
    def __init__(self):
        self.tenant_id = settings.GRAPH_TENANT_ID
        self.client_id = settings.GRAPH_CLIENT_ID
        self.client_secret = settings.GRAPH_CLIENT_SECRET
        self.mailboxes = settings.GRAPH_USER_MAILBOXES
        
        # MSAL app for authentication
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
        
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    async def _get_access_token(self) -> str:
        """Get or refresh access token."""
        now = datetime.now(timezone.utc)
        
        # Check if token is still valid (with 5 minute buffer)
        if (self._access_token and self._token_expires_at and 
            now < self._token_expires_at.replace(minute=self._token_expires_at.minute - 5)):
            return self._access_token
        
        # Get new token
        result = self.app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        
        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            logger.error("Failed to acquire Graph API token", error=error)
            raise Exception(f"Failed to acquire token: {error}")
        
        self._access_token = result["access_token"]
        # Token typically expires in 3600 seconds
        expires_in = result.get("expires_in", 3600)
        self._token_expires_at = now.replace(second=now.second + expires_in)
        
        logger.info("Successfully refreshed Graph API token", expires_at=self._token_expires_at)
        return self._access_token
    
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> httpx.Response:
        """Make authenticated request to Graph API."""
        token = await self._get_access_token()
        
        headers = kwargs.get("headers", {})
        headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        kwargs["headers"] = headers
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, **kwargs)
            
            if response.status_code == 401:
                # Token might be expired, try once more
                logger.warning("Graph API returned 401, refreshing token")
                self._access_token = None
                token = await self._get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                
                response = await client.request(method, url, **kwargs)
            
            return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def list_unread_messages(
        self,
        mailbox: str,
        folder: str = "inbox",
        top: int = 50
    ) -> List[Dict[str, Any]]:
        """List unread messages from a mailbox."""
        encoded_mailbox = quote(mailbox)
        url = (
            f"https://graph.microsoft.com/v1.0/users/{encoded_mailbox}/"
            f"mailFolders/{folder}/messages"
        )
        
        params = {
            "$filter": "isRead eq false",
            "$top": top,
            "$orderby": "receivedDateTime desc",
            "$select": (
                "id,subject,sender,toRecipients,ccRecipients,bccRecipients,"
                "receivedDateTime,bodyPreview,body,hasAttachments,internetMessageId"
            )
        }
        
        try:
            response = await self._make_request("GET", url, params=params)
            response.raise_for_status()
            
            data = response.json()
            messages = data.get("value", [])
            
            logger.info(
                "Retrieved unread messages",
                mailbox=mailbox,
                folder=folder,
                count=len(messages)
            )
            
            return messages
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to retrieve messages",
                mailbox=mailbox,
                status_code=e.response.status_code,
                error=str(e)
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error retrieving messages",
                mailbox=mailbox,
                error=str(e)
            )
            raise
    
    async def get_message_attachments(
        self,
        mailbox: str,
        message_id: str
    ) -> List[Dict[str, Any]]:
        """Get attachments for a message."""
        encoded_mailbox = quote(mailbox)
        url = (
            f"https://graph.microsoft.com/v1.0/users/{encoded_mailbox}/"
            f"messages/{message_id}/attachments"
        )
        
        try:
            response = await self._make_request("GET", url)
            response.raise_for_status()
            
            data = response.json()
            attachments = data.get("value", [])
            
            logger.info(
                "Retrieved message attachments",
                mailbox=mailbox,
                message_id=message_id,
                count=len(attachments)
            )
            
            return attachments
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to retrieve attachments",
                mailbox=mailbox,
                message_id=message_id,
                status_code=e.response.status_code,
                error=str(e)
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error retrieving attachments",
                mailbox=mailbox,
                message_id=message_id,
                error=str(e)
            )
            return []
    
    async def mark_as_read(self, mailbox: str, message_id: str) -> bool:
        """Mark a message as read."""
        encoded_mailbox = quote(mailbox)
        url = (
            f"https://graph.microsoft.com/v1.0/users/{encoded_mailbox}/"
            f"messages/{message_id}"
        )
        
        data = {"isRead": True}
        
        try:
            response = await self._make_request("PATCH", url, json=data)
            response.raise_for_status()
            
            logger.info(
                "Marked message as read",
                mailbox=mailbox,
                message_id=message_id
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to mark message as read",
                mailbox=mailbox,
                message_id=message_id,
                error=str(e)
            )
            return False
    
    async def move_message(
        self,
        mailbox: str,
        message_id: str,
        destination_folder: str
    ) -> bool:
        """Move a message to a different folder."""
        encoded_mailbox = quote(mailbox)
        url = (
            f"https://graph.microsoft.com/v1.0/users/{encoded_mailbox}/"
            f"messages/{message_id}/move"
        )
        
        data = {"destinationId": destination_folder}
        
        try:
            response = await self._make_request("POST", url, json=data)
            response.raise_for_status()
            
            logger.info(
                "Moved message to folder",
                mailbox=mailbox,
                message_id=message_id,
                destination=destination_folder
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to move message",
                mailbox=mailbox,
                message_id=message_id,
                destination=destination_folder,
                error=str(e)
            )
            return False
    
    async def send_email(
        self,
        from_mailbox: str,
        to_recipients: List[str],
        subject: str,
        body: str,
        cc_recipients: Optional[List[str]] = None,
        bcc_recipients: Optional[List[str]] = None,
        is_html: bool = False
    ) -> bool:
        """Send an email message."""
        encoded_mailbox = quote(from_mailbox)
        url = f"https://graph.microsoft.com/v1.0/users/{encoded_mailbox}/sendMail"
        
        # Build recipient lists
        to_list = [{"emailAddress": {"address": email}} for email in to_recipients]
        cc_list = [{"emailAddress": {"address": email}} for email in (cc_recipients or [])]
        bcc_list = [{"emailAddress": {"address": email}} for email in (bcc_recipients or [])]
        
        message_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if is_html else "Text",
                    "content": body
                },
                "toRecipients": to_list,
            }
        }
        
        if cc_list:
            message_data["message"]["ccRecipients"] = cc_list
        if bcc_list:
            message_data["message"]["bccRecipients"] = bcc_list
        
        try:
            response = await self._make_request("POST", url, json=message_data)
            response.raise_for_status()
            
            logger.info(
                "Email sent successfully",
                from_mailbox=from_mailbox,
                to_count=len(to_recipients),
                subject=subject[:50]
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send email",
                from_mailbox=from_mailbox,
                to_recipients=to_recipients,
                subject=subject,
                error=str(e)
            )
            return False
    
    def parse_graph_message(self, message_data: Dict[str, Any], mailbox: str) -> EmailMessage:
        """Parse Graph API message data into EmailMessage model."""
        # Extract recipient emails
        def extract_emails(recipients_list):
            if not recipients_list:
                return []
            return [r.get("emailAddress", {}).get("address", "") for r in recipients_list]
        
        to_emails = extract_emails(message_data.get("toRecipients", []))
        cc_emails = extract_emails(message_data.get("ccRecipients", []))
        bcc_emails = extract_emails(message_data.get("bccRecipients", []))
        
        # Parse sender
        sender_info = message_data.get("sender", {}).get("emailAddress", {})
        sender_email = sender_info.get("address", "")
        sender_name = sender_info.get("name", "")
        
        # Parse dates
        received_at = datetime.fromisoformat(
            message_data.get("receivedDateTime", "").replace("Z", "+00:00")
        )
        
        # Parse body
        body_data = message_data.get("body", {})
        body_content = body_data.get("content", "")
        body_type = body_data.get("contentType", "Text")
        
        # Create EmailMessage object
        email_message = EmailMessage(
            message_id=message_data.get("internetMessageId", ""),
            graph_id=message_data.get("id", ""),
            subject=clean_subject_line(message_data.get("subject", "")),
            sender_email=sender_email,
            sender_name=sender_name,
            recipient_emails=json.dumps(to_emails),
            cc_emails=json.dumps(cc_emails) if cc_emails else None,
            bcc_emails=json.dumps(bcc_emails) if bcc_emails else None,
            body_text=sanitize_input(body_content) if body_type == "Text" else None,
            body_html=body_content if body_type == "HTML" else None,
            received_at=received_at,
            mailbox=mailbox,
            is_processed=False
        )
        
        return email_message
    
    async def check_connection(self) -> bool:
        """Check if Graph API connection is working."""
        try:
            token = await self._get_access_token()
            
            # Try to access the first mailbox
            if not self.mailboxes:
                logger.warning("No mailboxes configured")
                return False
            
            mailbox = self.mailboxes[0]
            encoded_mailbox = quote(mailbox)
            url = f"https://graph.microsoft.com/v1.0/users/{encoded_mailbox}/mailFolders/inbox"
            
            response = await self._make_request("GET", url)
            response.raise_for_status()
            
            logger.info("Graph API connection test successful", mailbox=mailbox)
            return True
            
        except Exception as e:
            logger.error("Graph API connection test failed", error=str(e))
            return False