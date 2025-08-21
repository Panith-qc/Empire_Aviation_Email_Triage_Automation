"""Main email processing pipeline."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db_session
from app.models.email import EmailMessage, EmailAttachment
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from app.models.activity import ActivityLog, ActivityType
from app.models.message_state import MessageState, ProcessingStatus
from app.connectors.email_graph import GraphEmailConnector
from app.connectors.email_imap import IMAPEmailConnector
from app.connectors.email_smtp import SMTPEmailConnector
from app.classifier.rules_engine import RulesClassifier, ClassificationResult
from app.classifier.ml_classifier import MLClassifier
from app.escalation.engine import EscalationEngine
from app.utils.logging import get_logger, log_email_processing, CorrelationContextManager
from app.utils.security import hash_content, generate_secure_id
from app.utils.validation import (
    validate_email, 
    extract_aircraft_registration,
    extract_phone_numbers,
    sanitize_input
)

logger = get_logger(__name__)


class EmailProcessingPipeline:
    """Main pipeline for processing incoming emails."""
    
    def __init__(self):
        self.graph_connector = GraphEmailConnector()
        self.imap_connector = IMAPEmailConnector()
        self.smtp_connector = SMTPEmailConnector()
        self.rules_classifier = RulesClassifier()
        self.ml_classifier = MLClassifier() if settings.ENABLE_ML_CLASSIFICATION else None
        self.escalation_engine = EscalationEngine()
        
        # Load ML model if enabled
        if self.ml_classifier:
            self.ml_classifier.load_model()
    
    async def process_all_mailboxes(self) -> Dict[str, Any]:
        """Process all configured mailboxes."""
        results = {
            "total_processed": 0,
            "total_errors": 0,
            "mailbox_results": {}
        }
        
        mailboxes = settings.GRAPH_USER_MAILBOXES
        if not mailboxes:
            logger.warning("No mailboxes configured for processing")
            return results
        
        for mailbox in mailboxes:
            try:
                mailbox_result = await self.process_mailbox(mailbox)
                results["mailbox_results"][mailbox] = mailbox_result
                results["total_processed"] += mailbox_result.get("processed", 0)
                results["total_errors"] += mailbox_result.get("errors", 0)
                
            except Exception as e:
                logger.error("Error processing mailbox", mailbox=mailbox, error=str(e))
                results["total_errors"] += 1
                results["mailbox_results"][mailbox] = {
                    "processed": 0,
                    "errors": 1,
                    "error": str(e)
                }
        
        logger.info("Completed processing all mailboxes",
                   total_processed=results["total_processed"],
                   total_errors=results["total_errors"])
        
        return results
    
    async def process_mailbox(self, mailbox: str) -> Dict[str, Any]:
        """Process a single mailbox."""
        result = {
            "mailbox": mailbox,
            "processed": 0,
            "errors": 0,
            "skipped": 0,
            "tickets_created": 0
        }
        
        try:
            # Fetch unread messages
            messages = await self._fetch_unread_messages(mailbox)
            
            if not messages:
                logger.info("No unread messages found", mailbox=mailbox)
                return result
            
            logger.info("Found unread messages", mailbox=mailbox, count=len(messages))
            
            # Process each message
            for message_data in messages:
                try:
                    with CorrelationContextManager() as correlation_id:
                        message_result = await self._process_single_message(
                            message_data, 
                            mailbox,
                            correlation_id
                        )
                        
                        if message_result["status"] == "processed":
                            result["processed"] += 1
                            if message_result.get("ticket_created"):
                                result["tickets_created"] += 1
                        elif message_result["status"] == "skipped":
                            result["skipped"] += 1
                        else:
                            result["errors"] += 1
                
                except Exception as e:
                    logger.error("Error processing message", 
                               mailbox=mailbox,
                               message_id=message_data.get("id"),
                               error=str(e))
                    result["errors"] += 1
                
                # Small delay between messages to avoid overwhelming systems
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error("Error processing mailbox", mailbox=mailbox, error=str(e))
            result["errors"] += 1
        
        return result
    
    async def _fetch_unread_messages(self, mailbox: str) -> List[Dict[str, Any]]:
        """Fetch unread messages from mailbox."""
        try:
            # Try Graph API first
            if settings.GRAPH_TENANT_ID and settings.GRAPH_CLIENT_ID:
                return await self.graph_connector.list_unread_messages(
                    mailbox, 
                    top=settings.MAX_EMAILS_PER_BATCH
                )
            else:
                logger.warning("Graph API not configured, using IMAP fallback")
                # IMAP would need credentials per mailbox - placeholder for now
                return []
                
        except Exception as e:
            logger.error("Error fetching messages", mailbox=mailbox, error=str(e))
            return []
    
    async def _process_single_message(
        self, 
        message_data: Dict[str, Any], 
        mailbox: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Process a single email message."""
        message_id = message_data.get("internetMessageId", "")
        graph_id = message_data.get("id", "")
        
        log_email_processing(logger, graph_id, message_id, "starting_processing")
        
        async with get_db_session() as session:
            try:
                # Check if message already processed (idempotency)
                existing_state = await self._get_message_state(session, message_id)
                if existing_state and existing_state.is_complete:
                    log_email_processing(logger, graph_id, message_id, "already_processed")
                    return {"status": "skipped", "reason": "already_processed"}
                
                # Create or update message state
                message_state = await self._create_or_update_message_state(
                    session, message_id, graph_id, ProcessingStatus.PARSING
                )
                
                # Parse email message
                email_message = await self._parse_email_message(
                    session, message_data, mailbox
                )
                
                if not email_message:
                    await self._update_message_state(
                        session, message_state, ProcessingStatus.FAILED, "Failed to parse email"
                    )
                    return {"status": "error", "reason": "parse_failed"}
                
                log_email_processing(logger, graph_id, message_id, "parsed_email")
                
                # Update message state
                await self._update_message_state(
                    session, message_state, ProcessingStatus.CLASSIFYING
                )
                
                # Classify email
                classification = await self._classify_email(email_message)
                
                log_email_processing(
                    logger, graph_id, message_id, "classified_email",
                    category=classification.category.value,
                    priority=classification.priority.value,
                    confidence=classification.confidence
                )
                
                # Check if this is a service request
                if not self._is_service_request(classification):
                    # Mark as read and skip
                    await self._mark_message_as_read(mailbox, graph_id)
                    await self._update_message_state(
                        session, message_state, ProcessingStatus.SKIPPED, "Not a service request"
                    )
                    return {"status": "skipped", "reason": "not_service_request"}
                
                # Update message state
                await self._update_message_state(
                    session, message_state, ProcessingStatus.CREATING_TICKET
                )
                
                # Create ticket
                ticket = await self._create_ticket(session, email_message, classification)
                
                log_email_processing(
                    logger, graph_id, message_id, "created_ticket",
                    ticket_id=str(ticket.id),
                    ticket_number=ticket.ticket_number
                )
                
                # Update message state
                await self._update_message_state(
                    session, message_state, ProcessingStatus.SENDING_CONFIRMATION
                )
                
                # Send confirmation email to customer
                confirmation_sent = await self._send_customer_confirmation(ticket)
                
                if confirmation_sent:
                    await self._log_activity(
                        session, ticket.id, ActivityType.CONFIRMATION_SENT,
                        "Confirmation email sent to customer"
                    )
                
                # Update message state
                await self._update_message_state(
                    session, message_state, ProcessingStatus.SCHEDULING_ESCALATION
                )
                
                # Start escalation if enabled
                if settings.ENABLE_ESCALATION:
                    escalation_started = await self.escalation_engine.start_escalation(ticket.id)
                    
                    if escalation_started:
                        await self._log_activity(
                            session, ticket.id, ActivityType.ESCALATION_STARTED,
                            "Escalation process started"
                        )
                
                # Mark message as read
                await self._mark_message_as_read(mailbox, graph_id)
                
                # Update message as processed
                email_message.is_processed = True
                email_message.processed_at = datetime.utcnow()
                
                # Complete processing
                await self._update_message_state(
                    session, message_state, ProcessingStatus.COMPLETED
                )
                
                log_email_processing(
                    logger, graph_id, message_id, "processing_completed",
                    ticket_id=str(ticket.id)
                )
                
                return {
                    "status": "processed",
                    "ticket_id": str(ticket.id),
                    "ticket_number": ticket.ticket_number,
                    "ticket_created": True,
                    "confirmation_sent": confirmation_sent
                }
                
            except Exception as e:
                logger.error("Error in message processing pipeline",
                           message_id=message_id,
                           error=str(e))
                
                # Update message state to failed
                if 'message_state' in locals():
                    await self._update_message_state(
                        session, message_state, ProcessingStatus.FAILED, str(e)
                    )
                
                return {"status": "error", "reason": str(e)}
    
    async def _get_message_state(
        self, 
        session: AsyncSession, 
        message_id: str
    ) -> Optional[MessageState]:
        """Get existing message state."""
        result = await session.execute(
            select(MessageState).where(MessageState.message_id == message_id)
        )
        return result.scalar_one_or_none()
    
    async def _create_or_update_message_state(
        self,
        session: AsyncSession,
        message_id: str,
        graph_id: str,
        status: ProcessingStatus
    ) -> MessageState:
        """Create or update message state."""
        existing_state = await self._get_message_state(session, message_id)
        
        if existing_state:
            existing_state.status = status
            existing_state.processing_started_at = datetime.utcnow()
            return existing_state
        else:
            message_state = MessageState(
                message_id=message_id,
                graph_id=graph_id,
                status=status,
                processing_started_at=datetime.utcnow()
            )
            session.add(message_state)
            return message_state
    
    async def _update_message_state(
        self,
        session: AsyncSession,
        message_state: MessageState,
        status: ProcessingStatus,
        error: Optional[str] = None
    ) -> None:
        """Update message state."""
        message_state.status = status
        
        if error:
            message_state.error_count += 1
            message_state.last_error = error
        
        if status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.SKIPPED]:
            message_state.processing_completed_at = datetime.utcnow()
    
    async def _parse_email_message(
        self,
        session: AsyncSession,
        message_data: Dict[str, Any],
        mailbox: str
    ) -> Optional[EmailMessage]:
        """Parse email message data into EmailMessage model."""
        try:
            # Use Graph connector to parse message
            email_message = self.graph_connector.parse_graph_message(message_data, mailbox)
            
            # Generate content hash for idempotency
            content = f"{email_message.subject}{email_message.body_text or ''}{email_message.body_html or ''}"
            email_message.content_hash = hash_content(content)
            
            # Save to database
            session.add(email_message)
            
            # Handle attachments if present
            if message_data.get("hasAttachments"):
                await self._save_attachments(session, email_message, message_data, mailbox)
            
            return email_message
            
        except Exception as e:
            logger.error("Error parsing email message", error=str(e))
            return None
    
    async def _save_attachments(
        self,
        session: AsyncSession,
        email_message: EmailMessage,
        message_data: Dict[str, Any],
        mailbox: str
    ) -> None:
        """Save email attachments."""
        try:
            graph_id = message_data.get("id", "")
            attachments_data = await self.graph_connector.get_message_attachments(mailbox, graph_id)
            
            for attachment_data in attachments_data:
                attachment = EmailAttachment(
                    email_message_id=email_message.id,
                    filename=attachment_data.get("name", "unknown"),
                    content_type=attachment_data.get("contentType", "application/octet-stream"),
                    size_bytes=attachment_data.get("size", 0)
                )
                
                # In a production system, you'd save the actual attachment content
                # For now, we just store metadata
                session.add(attachment)
                
        except Exception as e:
            logger.error("Error saving attachments", error=str(e))
    
    async def _classify_email(self, email_message: EmailMessage) -> ClassificationResult:
        """Classify email using rules and optionally ML."""
        # Get email content
        subject = email_message.subject or ""
        body = email_message.body_text or email_message.body_html or ""
        sender_email = email_message.sender_email
        
        # Parse recipient emails from JSON
        try:
            recipient_emails = json.loads(email_message.recipient_emails or "[]")
            attachments = []  # Would get from attachments relationship
        except:
            recipient_emails = []
            attachments = []
        
        # Use rules classifier
        rules_result = self.rules_classifier.classify_email(
            subject, body, sender_email, attachments
        )
        
        # Use ML classifier if available and rules confidence is low
        if (self.ml_classifier and 
            rules_result.confidence < 0.8):
            
            ml_result = self.ml_classifier.classify_email(
                subject, body, sender_email, attachments
            )
            
            if ml_result and ml_result.confidence > rules_result.confidence:
                logger.info("Using ML classification over rules",
                           rules_confidence=rules_result.confidence,
                           ml_confidence=ml_result.confidence)
                return ml_result
        
        return rules_result
    
    def _is_service_request(self, classification: ClassificationResult) -> bool:
        """Determine if email is a service request that should create a ticket."""
        # Skip general inquiries with low confidence
        if (classification.category == TicketCategory.GENERAL and 
            classification.confidence < 0.6):
            return False
        
        # Always process AOG requests
        if classification.is_aog:
            return True
        
        # Process service and maintenance requests
        if classification.category in [TicketCategory.SERVICE, TicketCategory.MAINTENANCE]:
            return True
        
        # Process invoice requests with reasonable confidence
        if (classification.category == TicketCategory.INVOICE and 
            classification.confidence > 0.7):
            return True
        
        # Process general inquiries with high confidence
        if (classification.category == TicketCategory.GENERAL and 
            classification.confidence > 0.8):
            return True
        
        return False
    
    async def _create_ticket(
        self,
        session: AsyncSession,
        email_message: EmailMessage,
        classification: ClassificationResult
    ) -> Ticket:
        """Create a ticket from email message and classification."""
        # Generate ticket number
        ticket_number = await self._generate_ticket_number(session)
        
        # Extract customer information
        customer_name = email_message.sender_name or ""
        customer_phone = None
        
        # Try to extract phone from email body
        body_text = email_message.body_text or ""
        phone_numbers = extract_phone_numbers(body_text)
        if phone_numbers:
            customer_phone = phone_numbers[0]
        
        # Calculate SLA times
        now = datetime.utcnow()
        response_due_at = self._calculate_response_sla(now, classification.priority)
        resolution_due_at = self._calculate_resolution_sla(now, classification.priority)
        
        # Create ticket
        ticket = Ticket(
            ticket_number=ticket_number,
            email_message_id=email_message.id,
            title=email_message.subject or "Service Request",
            description=email_message.body_text or email_message.body_html,
            category=classification.category,
            priority=classification.priority,
            status=TicketStatus.NEW,
            customer_email=email_message.sender_email,
            customer_name=customer_name,
            customer_phone=customer_phone,
            aircraft_registration=classification.aircraft_registration,
            response_due_at=response_due_at,
            resolution_due_at=resolution_due_at
        )
        
        session.add(ticket)
        
        # Log ticket creation
        await self._log_activity(
            session,
            ticket.id,
            ActivityType.TICKET_CREATED,
            f"Ticket created from email: {email_message.subject}",
            {
                "classification": {
                    "category": classification.category.value,
                    "priority": classification.priority.value,
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning
                }
            }
        )
        
        return ticket
    
    async def _generate_ticket_number(self, session: AsyncSession) -> str:
        """Generate unique ticket number."""
        # Simple format: EMB-YYYYMMDD-NNNN
        today = datetime.utcnow()
        date_prefix = today.strftime("%Y%m%d")
        
        # Count tickets created today
        result = await session.execute(
            select(Ticket)
            .where(Ticket.created_at >= today.replace(hour=0, minute=0, second=0, microsecond=0))
        )
        
        count = len(result.scalars().all())
        sequence = str(count + 1).zfill(4)
        
        return f"EMB-{date_prefix}-{sequence}"
    
    def _calculate_response_sla(self, created_at: datetime, priority: TicketPriority) -> datetime:
        """Calculate response SLA deadline."""
        if priority == TicketPriority.CRITICAL:
            return created_at + timedelta(minutes=15)
        elif priority == TicketPriority.HIGH:
            return created_at + timedelta(hours=1)
        elif priority == TicketPriority.NORMAL:
            return created_at + timedelta(hours=4)
        else:  # LOW
            return created_at + timedelta(hours=8)
    
    def _calculate_resolution_sla(self, created_at: datetime, priority: TicketPriority) -> datetime:
        """Calculate resolution SLA deadline."""
        if priority == TicketPriority.CRITICAL:
            return created_at + timedelta(hours=2)
        elif priority == TicketPriority.HIGH:
            return created_at + timedelta(hours=8)
        elif priority == TicketPriority.NORMAL:
            return created_at + timedelta(hours=24)
        else:  # LOW
            return created_at + timedelta(hours=48)
    
    async def _send_customer_confirmation(self, ticket: Ticket) -> bool:
        """Send confirmation email to customer."""
        try:
            return await self.smtp_connector.send_confirmation_email(
                customer_email=ticket.customer_email,
                customer_name=ticket.customer_name,
                ticket_number=ticket.ticket_number,
                subject=ticket.title,
                category=ticket.category.value,
                priority=ticket.priority.value
            )
        except Exception as e:
            logger.error("Error sending confirmation email",
                        ticket_id=str(ticket.id),
                        error=str(e))
            return False
    
    async def _mark_message_as_read(self, mailbox: str, graph_id: str) -> bool:
        """Mark email message as read."""
        try:
            return await self.graph_connector.mark_as_read(mailbox, graph_id)
        except Exception as e:
            logger.error("Error marking message as read",
                        mailbox=mailbox,
                        graph_id=graph_id,
                        error=str(e))
            return False
    
    async def _log_activity(
        self,
        session: AsyncSession,
        ticket_id: UUID,
        activity_type: ActivityType,
        title: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log activity for audit trail."""
        activity = ActivityLog(
            ticket_id=ticket_id,
            activity_type=activity_type,
            title=title,
            actor_type="system",
            actor_id="email_pipeline",
            metadata=json.dumps(metadata) if metadata else None,
            is_success=True
        )
        session.add(activity)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on pipeline components."""
        health_status = {
            "pipeline": "healthy",
            "components": {}
        }
        
        try:
            # Check Graph API connection
            graph_ok = await self.graph_connector.check_connection()
            health_status["components"]["graph_api"] = "healthy" if graph_ok else "unhealthy"
            
            # Check SMTP connection
            smtp_ok = await self.smtp_connector.check_connection()
            health_status["components"]["smtp"] = "healthy" if smtp_ok else "unhealthy"
            
            # Check Twilio connection (through escalation engine)
            twilio_ok = await self.escalation_engine.sms_connector.check_connection()
            health_status["components"]["twilio"] = "healthy" if twilio_ok else "unhealthy"
            
            # Check if any critical components are down
            critical_components = ["graph_api", "smtp"]
            if any(health_status["components"][comp] == "unhealthy" for comp in critical_components):
                health_status["pipeline"] = "degraded"
            
        except Exception as e:
            logger.error("Error in pipeline health check", error=str(e))
            health_status["pipeline"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status