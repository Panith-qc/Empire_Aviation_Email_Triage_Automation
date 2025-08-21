"""IMAP email connector as fallback for Graph API."""

import asyncio
import email
import imaplib
import ssl
from datetime import datetime
from email.header import decode_header
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.utils.logging import get_logger
from app.utils.validation import clean_subject_line, sanitize_input

logger = get_logger(__name__)


class IMAPEmailConnector:
    """IMAP connector as fallback for Graph API."""
    
    def __init__(self):
        self.host = "outlook.office365.com"  # Default for Office 365
        self.port = 993
        self.use_ssl = True
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    async def connect(self, username: str, password: str) -> Optional[imaplib.IMAP4_SSL]:
        """Create IMAP connection."""
        def _connect():
            try:
                if self.use_ssl:
                    mail = imaplib.IMAP4_SSL(self.host, self.port)
                else:
                    mail = imaplib.IMAP4(self.host, self.port)
                
                mail.login(username, password)
                return mail
                
            except Exception as e:
                logger.error(
                    "IMAP connection failed",
                    host=self.host,
                    username=username,
                    error=str(e)
                )
                return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _connect)
    
    async def list_unread_messages(
        self,
        username: str,
        password: str,
        folder: str = "INBOX",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List unread messages via IMAP."""
        def _fetch_messages():
            mail = None
            try:
                # Connect
                if self.use_ssl:
                    mail = imaplib.IMAP4_SSL(self.host, self.port)
                else:
                    mail = imaplib.IMAP4(self.host, self.port)
                
                mail.login(username, password)
                mail.select(folder)
                
                # Search for unread messages
                status, messages = mail.search(None, 'UNSEEN')
                
                if status != 'OK':
                    logger.error("IMAP search failed", status=status)
                    return []
                
                message_ids = messages[0].split()
                
                # Limit number of messages
                if limit and len(message_ids) > limit:
                    message_ids = message_ids[-limit:]  # Get most recent
                
                parsed_messages = []
                
                for msg_id in message_ids:
                    try:
                        # Fetch message
                        status, msg_data = mail.fetch(msg_id, '(RFC822)')
                        
                        if status != 'OK':
                            continue
                        
                        # Parse email
                        raw_email = msg_data[0][1]
                        email_message = email.message_from_bytes(raw_email)
                        
                        parsed_msg = self._parse_email_message(email_message, msg_id.decode())
                        if parsed_msg:
                            parsed_messages.append(parsed_msg)
                            
                    except Exception as e:
                        logger.error(
                            "Error parsing IMAP message",
                            message_id=msg_id,
                            error=str(e)
                        )
                        continue
                
                return parsed_messages
                
            except Exception as e:
                logger.error(
                    "IMAP fetch failed",
                    username=username,
                    error=str(e)
                )
                return []
            finally:
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except:
                        pass
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _fetch_messages)
    
    def _parse_email_message(self, email_msg: email.message.Message, imap_id: str) -> Optional[Dict[str, Any]]:
        """Parse email message into standard format."""
        try:
            # Extract headers
            subject = self._decode_header(email_msg.get("Subject", ""))
            from_header = self._decode_header(email_msg.get("From", ""))
            to_header = self._decode_header(email_msg.get("To", ""))
            cc_header = self._decode_header(email_msg.get("Cc", ""))
            date_header = email_msg.get("Date", "")
            message_id = email_msg.get("Message-ID", f"imap-{imap_id}")
            
            # Parse sender
            sender_email, sender_name = self._parse_email_address(from_header)
            
            # Parse recipients
            to_recipients = self._parse_email_addresses(to_header)
            cc_recipients = self._parse_email_addresses(cc_header)
            
            # Parse date
            try:
                received_at = email.utils.parsedate_to_datetime(date_header)
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=datetime.now().astimezone().tzinfo)
            except:
                received_at = datetime.now()
            
            # Extract body
            body_text, body_html = self._extract_body(email_msg)
            
            # Check for attachments
            has_attachments = any(
                part.get_content_disposition() == "attachment"
                for part in email_msg.walk()
            )
            
            return {
                "id": imap_id,
                "internetMessageId": message_id,
                "subject": clean_subject_line(subject),
                "sender": {
                    "emailAddress": {
                        "address": sender_email,
                        "name": sender_name
                    }
                },
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in to_recipients
                ],
                "ccRecipients": [
                    {"emailAddress": {"address": addr}} for addr in cc_recipients
                ] if cc_recipients else [],
                "receivedDateTime": received_at.isoformat(),
                "body": {
                    "content": body_html or body_text or "",
                    "contentType": "HTML" if body_html else "Text"
                },
                "bodyPreview": (body_text or body_html or "")[:150],
                "hasAttachments": has_attachments
            }
            
        except Exception as e:
            logger.error(
                "Error parsing email message",
                imap_id=imap_id,
                error=str(e)
            )
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ""
        
        try:
            decoded_parts = decode_header(header)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += part
            
            return decoded_string
            
        except Exception as e:
            logger.warning(
                "Error decoding header",
                header=header[:100],
                error=str(e)
            )
            return header
    
    def _parse_email_address(self, address_str: str) -> tuple[str, str]:
        """Parse email address from header."""
        if not address_str:
            return "", ""
        
        try:
            parsed = email.utils.parseaddr(address_str)
            name, addr = parsed
            return addr.strip(), name.strip()
        except:
            return address_str.strip(), ""
    
    def _parse_email_addresses(self, addresses_str: str) -> List[str]:
        """Parse multiple email addresses from header."""
        if not addresses_str:
            return []
        
        try:
            addresses = email.utils.getaddresses([addresses_str])
            return [addr for name, addr in addresses if addr]
        except:
            return []
    
    def _extract_body(self, email_msg: email.message.Message) -> tuple[Optional[str], Optional[str]]:
        """Extract text and HTML body from email."""
        body_text = None
        body_html = None
        
        try:
            if email_msg.is_multipart():
                for part in email_msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = part.get_content_disposition()
                    
                    # Skip attachments
                    if content_disposition == "attachment":
                        continue
                    
                    if content_type == "text/plain" and not body_text:
                        body_text = self._get_part_content(part)
                    elif content_type == "text/html" and not body_html:
                        body_html = self._get_part_content(part)
            else:
                content_type = email_msg.get_content_type()
                if content_type == "text/plain":
                    body_text = self._get_part_content(email_msg)
                elif content_type == "text/html":
                    body_html = self._get_part_content(email_msg)
        
        except Exception as e:
            logger.error("Error extracting email body", error=str(e))
        
        # Sanitize content
        if body_text:
            body_text = sanitize_input(body_text, max_length=10000)
        if body_html:
            body_html = sanitize_input(body_html, max_length=20000)
        
        return body_text, body_html
    
    def _get_part_content(self, part: email.message.Message) -> Optional[str]:
        """Get content from email part."""
        try:
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                # Try to decode with specified charset
                charset = part.get_content_charset() or 'utf-8'
                try:
                    return payload.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    # Fallback to utf-8 with error handling
                    return payload.decode('utf-8', errors='ignore')
            else:
                return str(payload)
        except Exception as e:
            logger.error("Error decoding email part content", error=str(e))
            return None
    
    async def mark_as_read(
        self,
        username: str,
        password: str,
        message_id: str,
        folder: str = "INBOX"
    ) -> bool:
        """Mark message as read via IMAP."""
        def _mark_read():
            mail = None
            try:
                if self.use_ssl:
                    mail = imaplib.IMAP4_SSL(self.host, self.port)
                else:
                    mail = imaplib.IMAP4(self.host, self.port)
                
                mail.login(username, password)
                mail.select(folder)
                
                # Add \Seen flag
                mail.store(message_id, '+FLAGS', '\\Seen')
                
                return True
                
            except Exception as e:
                logger.error(
                    "Error marking message as read",
                    message_id=message_id,
                    error=str(e)
                )
                return False
            finally:
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except:
                        pass
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _mark_read)
    
    async def check_connection(self, username: str, password: str) -> bool:
        """Test IMAP connection."""
        def _test_connection():
            mail = None
            try:
                if self.use_ssl:
                    mail = imaplib.IMAP4_SSL(self.host, self.port)
                else:
                    mail = imaplib.IMAP4(self.host, self.port)
                
                mail.login(username, password)
                mail.select("INBOX")
                
                return True
                
            except Exception as e:
                logger.error(
                    "IMAP connection test failed",
                    username=username,
                    error=str(e)
                )
                return False
            finally:
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except:
                        pass
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _test_connection)