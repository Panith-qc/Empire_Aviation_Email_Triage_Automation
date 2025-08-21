"""Escalation engine for managing automated escalations."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db_session
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.escalation import EscalationStep, EscalationStatus, EscalationChannel
from app.models.activity import ActivityLog, ActivityType
from app.connectors.email_smtp import SMTPEmailConnector
from app.connectors.twilio_sms import TwilioSMSConnector
from app.escalation.contacts import ContactManager
from app.utils.logging import get_logger, log_escalation_event

logger = get_logger(__name__)


class EscalationEngine:
    """Engine for managing automated escalations."""
    
    def __init__(self):
        self.email_connector = SMTPEmailConnector()
        self.sms_connector = TwilioSMSConnector()
        self.contact_manager = ContactManager()
        
        # Escalation intervals by priority (minutes)
        self.escalation_intervals = {
            TicketPriority.CRITICAL: settings.ESCALATION_WINDOW_MINUTES[0] if len(settings.ESCALATION_WINDOW_MINUTES) > 0 else 15,
            TicketPriority.HIGH: settings.ESCALATION_WINDOW_MINUTES[1] if len(settings.ESCALATION_WINDOW_MINUTES) > 1 else 60,
            TicketPriority.NORMAL: settings.ESCALATION_WINDOW_MINUTES[2] if len(settings.ESCALATION_WINDOW_MINUTES) > 2 else 240,
            TicketPriority.LOW: 480  # 8 hours
        }
    
    async def start_escalation(self, ticket_id: UUID) -> bool:
        """Start escalation process for a ticket."""
        try:
            async with get_db_session() as session:
                # Get ticket details
                result = await session.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )
                ticket = result.scalar_one_or_none()
                
                if not ticket:
                    logger.error("Ticket not found for escalation", ticket_id=ticket_id)
                    return False
                
                if ticket.escalation_stopped:
                    logger.info("Escalation already stopped", ticket_id=ticket_id)
                    return False
                
                # Get escalation contacts for this ticket
                contacts = await self.contact_manager.get_escalation_contacts(
                    ticket.category,
                    ticket.priority
                )
                
                if not contacts:
                    logger.warning("No escalation contacts found", 
                                 ticket_id=ticket_id, 
                                 category=ticket.category,
                                 priority=ticket.priority)
                    return False
                
                # Create escalation steps
                await self._create_escalation_steps(session, ticket, contacts)
                
                # Schedule first escalation
                await self._schedule_next_escalation(session, ticket)
                
                # Log activity
                await self._log_activity(
                    session,
                    ticket_id,
                    ActivityType.ESCALATION_STARTED,
                    "Escalation process started",
                    {"contact_count": len(contacts)}
                )
                
                logger.info("Escalation started", 
                           ticket_id=ticket_id,
                           priority=ticket.priority,
                           contact_count=len(contacts))
                
                return True
                
        except Exception as e:
            logger.error("Error starting escalation", ticket_id=ticket_id, error=str(e))
            return False
    
    async def stop_escalation(
        self, 
        ticket_id: UUID, 
        reason: str = "Internal response received"
    ) -> bool:
        """Stop escalation process for a ticket."""
        try:
            async with get_db_session() as session:
                # Update ticket
                result = await session.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )
                ticket = result.scalar_one_or_none()
                
                if not ticket:
                    logger.error("Ticket not found", ticket_id=ticket_id)
                    return False
                
                if ticket.escalation_stopped:
                    logger.info("Escalation already stopped", ticket_id=ticket_id)
                    return True
                
                # Stop escalation
                ticket.escalation_stopped = True
                ticket.escalation_stopped_reason = reason
                
                # Update pending escalation steps
                await session.execute(
                    EscalationStep.__table__.update()
                    .where(
                        and_(
                            EscalationStep.ticket_id == ticket_id,
                            EscalationStep.status == EscalationStatus.PENDING
                        )
                    )
                    .values(status=EscalationStatus.SKIPPED)
                )
                
                # Log activity
                await self._log_activity(
                    session,
                    ticket_id,
                    ActivityType.ESCALATION_STOPPED,
                    f"Escalation stopped: {reason}"
                )
                
                log_escalation_event(
                    logger,
                    str(ticket_id),
                    ticket.escalation_level,
                    "all",
                    "stopped"
                )
                
                return True
                
        except Exception as e:
            logger.error("Error stopping escalation", ticket_id=ticket_id, error=str(e))
            return False
    
    async def process_pending_escalations(self) -> int:
        """Process all pending escalations that are due."""
        processed_count = 0
        
        try:
            async with get_db_session() as session:
                # Find escalation steps that should be executed
                now = datetime.utcnow()
                
                result = await session.execute(
                    select(EscalationStep, Ticket)
                    .join(Ticket, EscalationStep.ticket_id == Ticket.id)
                    .where(
                        and_(
                            EscalationStep.status == EscalationStatus.SCHEDULED,
                            EscalationStep.scheduled_at <= now,
                            Ticket.escalation_stopped == False
                        )
                    )
                    .order_by(EscalationStep.scheduled_at)
                )
                
                pending_steps = result.all()
                
                for step, ticket in pending_steps:
                    success = await self._execute_escalation_step(session, step, ticket)
                    if success:
                        processed_count += 1
                    
                    # Small delay between escalations to avoid overwhelming systems
                    await asyncio.sleep(0.5)
                
                if processed_count > 0:
                    logger.info("Processed pending escalations", count=processed_count)
                
        except Exception as e:
            logger.error("Error processing pending escalations", error=str(e))
        
        return processed_count
    
    async def _create_escalation_steps(
        self,
        session: AsyncSession,
        ticket: Ticket,
        contacts: List[Dict[str, Any]]
    ) -> None:
        """Create escalation steps for a ticket."""
        interval_minutes = self.escalation_intervals.get(ticket.priority, 60)
        current_time = datetime.utcnow()
        
        for i, contact in enumerate(contacts):
            step_number = i + 1
            scheduled_time = current_time + timedelta(minutes=interval_minutes * step_number)
            
            # Create email escalation step
            if contact.get('email'):
                email_step = EscalationStep(
                    ticket_id=ticket.id,
                    step_number=step_number,
                    status=EscalationStatus.SCHEDULED,
                    channel=EscalationChannel.EMAIL,
                    contact_email=contact['email'],
                    contact_name=contact.get('name'),
                    contact_role=contact.get('role'),
                    scheduled_at=scheduled_time,
                    subject=f"[Embassy Aviation] Escalation #{ticket.ticket_number} - {ticket.title}",
                    max_retries=3
                )
                session.add(email_step)
            
            # Create SMS escalation step (for critical tickets or if enabled)
            if (contact.get('phone') and 
                (ticket.priority == TicketPriority.CRITICAL or 
                 settings.ENABLE_SMS_ALERTS)):
                
                sms_step = EscalationStep(
                    ticket_id=ticket.id,
                    step_number=step_number,
                    status=EscalationStatus.SCHEDULED,
                    channel=EscalationChannel.SMS,
                    contact_phone=contact['phone'],
                    contact_name=contact.get('name'),
                    contact_role=contact.get('role'),
                    scheduled_at=scheduled_time,
                    message_body=f"Embassy Aviation Alert: Ticket #{ticket.ticket_number} needs attention",
                    max_retries=2
                )
                session.add(sms_step)
    
    async def _schedule_next_escalation(
        self,
        session: AsyncSession,
        ticket: Ticket
    ) -> None:
        """Schedule the next escalation step."""
        # Find the earliest scheduled step
        result = await session.execute(
            select(EscalationStep)
            .where(
                and_(
                    EscalationStep.ticket_id == ticket.id,
                    EscalationStep.status == EscalationStatus.SCHEDULED
                )
            )
            .order_by(EscalationStep.scheduled_at)
            .limit(1)
        )
        
        next_step = result.scalar_one_or_none()
        if next_step:
            logger.info("Next escalation scheduled",
                       ticket_id=ticket.id,
                       step=next_step.step_number,
                       scheduled_at=next_step.scheduled_at)
    
    async def _execute_escalation_step(
        self,
        session: AsyncSession,
        step: EscalationStep,
        ticket: Ticket
    ) -> bool:
        """Execute a single escalation step."""
        try:
            # Update step status
            step.status = EscalationStatus.PENDING
            
            success = False
            
            if step.channel == EscalationChannel.EMAIL:
                success = await self._send_escalation_email(step, ticket)
            elif step.channel == EscalationChannel.SMS:
                success = await self._send_escalation_sms(step, ticket)
            
            # Update step based on result
            if success:
                step.status = EscalationStatus.SENT
                step.sent_at = datetime.utcnow()
                
                # Update ticket escalation level
                ticket.escalation_level = max(ticket.escalation_level, step.step_number)
                ticket.last_escalated_at = datetime.utcnow()
                
                # Log activity
                await self._log_activity(
                    session,
                    ticket.id,
                    ActivityType.ESCALATION_STEP_EXECUTED,
                    f"Escalation step {step.step_number} sent via {step.channel.value}",
                    {
                        "step_number": step.step_number,
                        "channel": step.channel.value,
                        "contact": step.contact_email or step.contact_phone
                    }
                )
                
                log_escalation_event(
                    logger,
                    str(ticket.id),
                    step.step_number,
                    step.channel.value,
                    "sent"
                )
                
            else:
                step.status = EscalationStatus.FAILED
                step.retry_count += 1
                
                # Schedule retry if within retry limit
                if step.retry_count < step.max_retries:
                    step.status = EscalationStatus.SCHEDULED
                    step.scheduled_at = datetime.utcnow() + timedelta(minutes=5)  # Retry in 5 minutes
                
                log_escalation_event(
                    logger,
                    str(ticket.id),
                    step.step_number,
                    step.channel.value,
                    "failed"
                )
            
            return success
            
        except Exception as e:
            logger.error("Error executing escalation step",
                        step_id=step.id,
                        error=str(e))
            
            step.status = EscalationStatus.FAILED
            step.last_error = str(e)
            return False
    
    async def _send_escalation_email(
        self,
        step: EscalationStep,
        ticket: Ticket
    ) -> bool:
        """Send escalation email."""
        try:
            return await self.email_connector.send_escalation_email(
                to_recipients=[step.contact_email],
                ticket_number=ticket.ticket_number,
                customer_email=ticket.customer_email,
                subject=ticket.title,
                category=ticket.category.value,
                priority=ticket.priority.value,
                escalation_level=step.step_number,
                original_message=ticket.description or ""
            )
        except Exception as e:
            logger.error("Error sending escalation email",
                        step_id=step.id,
                        error=str(e))
            return False
    
    async def _send_escalation_sms(
        self,
        step: EscalationStep,
        ticket: Ticket
    ) -> bool:
        """Send escalation SMS."""
        try:
            message_id = await self.sms_connector.send_escalation_sms(
                to_number=step.contact_phone,
                ticket_number=ticket.ticket_number,
                customer_email=ticket.customer_email,
                category=ticket.category.value,
                priority=ticket.priority.value,
                escalation_level=step.step_number
            )
            
            if message_id:
                step.message_id = message_id
                return True
            
            return False
            
        except Exception as e:
            logger.error("Error sending escalation SMS",
                        step_id=step.id,
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
        """Log escalation activity."""
        activity = ActivityLog(
            ticket_id=ticket_id,
            activity_type=activity_type,
            title=title,
            actor_type="system",
            actor_id="escalation_engine",
            metadata=str(metadata) if metadata else None,
            is_success=True
        )
        session.add(activity)
    
    async def get_escalation_status(self, ticket_id: UUID) -> Dict[str, Any]:
        """Get escalation status for a ticket."""
        try:
            async with get_db_session() as session:
                # Get ticket
                result = await session.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )
                ticket = result.scalar_one_or_none()
                
                if not ticket:
                    return {"error": "Ticket not found"}
                
                # Get escalation steps
                result = await session.execute(
                    select(EscalationStep)
                    .where(EscalationStep.ticket_id == ticket_id)
                    .order_by(EscalationStep.step_number)
                )
                steps = result.scalars().all()
                
                return {
                    "ticket_id": str(ticket_id),
                    "escalation_stopped": ticket.escalation_stopped,
                    "escalation_level": ticket.escalation_level,
                    "last_escalated_at": ticket.last_escalated_at.isoformat() if ticket.last_escalated_at else None,
                    "steps": [
                        {
                            "step_number": step.step_number,
                            "status": step.status.value,
                            "channel": step.channel.value,
                            "contact": step.contact_email or step.contact_phone,
                            "scheduled_at": step.scheduled_at.isoformat() if step.scheduled_at else None,
                            "sent_at": step.sent_at.isoformat() if step.sent_at else None,
                            "retry_count": step.retry_count
                        }
                        for step in steps
                    ]
                }
                
        except Exception as e:
            logger.error("Error getting escalation status", ticket_id=ticket_id, error=str(e))
            return {"error": str(e)}