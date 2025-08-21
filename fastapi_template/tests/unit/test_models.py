"""Unit tests for database models."""

import pytest
from datetime import datetime, timedelta
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from app.models.email import EmailMessage
from app.models.escalation import EscalationStep, EscalationStatus, EscalationChannel


class TestTicketModel:
    """Test the Ticket model."""
    
    def test_ticket_creation(self, db_session):
        """Test basic ticket creation."""
        ticket = Ticket(
            ticket_number="EMB-20240115-0001",
            title="Test Service Request",
            description="Test description",
            category=TicketCategory.SERVICE,
            priority=TicketPriority.NORMAL,
            status=TicketStatus.NEW,
            customer_email="customer@example.com",
            customer_name="Test Customer"
        )
        
        assert ticket.ticket_number == "EMB-20240115-0001"
        assert ticket.category == TicketCategory.SERVICE
        assert ticket.priority == TicketPriority.NORMAL
        assert ticket.status == TicketStatus.NEW
    
    def test_is_aog_property(self):
        """Test the is_aog property."""
        # AOG category ticket
        aog_ticket = Ticket(
            ticket_number="EMB-20240115-0001",
            title="AOG Request",
            category=TicketCategory.AOG,
            priority=TicketPriority.CRITICAL,
            status=TicketStatus.NEW,
            customer_email="customer@example.com"
        )
        
        # Critical priority ticket
        critical_ticket = Ticket(
            ticket_number="EMB-20240115-0002", 
            title="Critical Request",
            category=TicketCategory.SERVICE,
            priority=TicketPriority.CRITICAL,
            status=TicketStatus.NEW,
            customer_email="customer@example.com"
        )
        
        # Normal ticket
        normal_ticket = Ticket(
            ticket_number="EMB-20240115-0003",
            title="Normal Request", 
            category=TicketCategory.SERVICE,
            priority=TicketPriority.NORMAL,
            status=TicketStatus.NEW,
            customer_email="customer@example.com"
        )
        
        assert aog_ticket.is_aog is True
        assert critical_ticket.is_aog is True
        assert normal_ticket.is_aog is False
    
    def test_is_overdue_property(self):
        """Test the is_overdue property."""
        now = datetime.utcnow()
        
        # Overdue ticket (response due in past, no response yet)
        overdue_ticket = Ticket(
            ticket_number="EMB-20240115-0001",
            title="Overdue Ticket",
            category=TicketCategory.SERVICE,
            priority=TicketPriority.NORMAL,
            status=TicketStatus.NEW,
            customer_email="customer@example.com",
            response_due_at=now - timedelta(hours=1),
            first_response_at=None
        )
        
        # Not overdue (already responded)
        responded_ticket = Ticket(
            ticket_number="EMB-20240115-0002",
            title="Responded Ticket",
            category=TicketCategory.SERVICE,
            priority=TicketPriority.NORMAL,
            status=TicketStatus.ASSIGNED,
            customer_email="customer@example.com",
            response_due_at=now - timedelta(hours=1),
            first_response_at=now - timedelta(minutes=30)
        )
        
        # Not overdue (still time)
        current_ticket = Ticket(
            ticket_number="EMB-20240115-0003",
            title="Current Ticket",
            category=TicketCategory.SERVICE,
            priority=TicketPriority.NORMAL,
            status=TicketStatus.NEW,
            customer_email="customer@example.com",
            response_due_at=now + timedelta(hours=1),
            first_response_at=None
        )
        
        assert overdue_ticket.is_overdue is True
        assert responded_ticket.is_overdue is False
        assert current_ticket.is_overdue is False


class TestEmailModel:
    """Test the EmailMessage model."""
    
    def test_email_creation(self):
        """Test basic email creation."""
        email = EmailMessage(
            message_id="test-message-123",
            graph_id="test-graph-123",
            subject="Test Email",
            sender_email="sender@example.com",
            sender_name="Test Sender",
            recipient_emails='["recipient@example.com"]',
            body_text="Test email body",
            received_at=datetime.utcnow(),
            mailbox="test@embassy-aviation.com"
        )
        
        assert email.message_id == "test-message-123"
        assert email.subject == "Test Email"
        assert email.sender_email == "sender@example.com"
        assert email.is_processed is False


class TestEscalationModel:
    """Test the EscalationStep model."""
    
    def test_escalation_step_creation(self):
        """Test basic escalation step creation."""
        step = EscalationStep(
            step_number=1,
            status=EscalationStatus.SCHEDULED,
            channel=EscalationChannel.EMAIL,
            contact_email="ops@embassy-aviation.com",
            contact_name="Operations Manager",
            scheduled_at=datetime.utcnow() + timedelta(minutes=15)
        )
        
        assert step.step_number == 1
        assert step.status == EscalationStatus.SCHEDULED
        assert step.channel == EscalationChannel.EMAIL
        assert step.retry_count == 0
    
    def test_can_retry_property(self):
        """Test the can_retry property."""
        # Failed step with retries available
        failed_step = EscalationStep(
            step_number=1,
            status=EscalationStatus.FAILED,
            channel=EscalationChannel.SMS,
            retry_count=1,
            max_retries=3
        )
        
        # Failed step with no retries left
        exhausted_step = EscalationStep(
            step_number=1,
            status=EscalationStatus.FAILED,
            channel=EscalationChannel.SMS,
            retry_count=3,
            max_retries=3
        )
        
        # Successful step
        success_step = EscalationStep(
            step_number=1,
            status=EscalationStatus.SENT,
            channel=EscalationChannel.EMAIL,
            retry_count=0,
            max_retries=3
        )
        
        assert failed_step.can_retry is True
        assert exhausted_step.can_retry is False
        assert success_step.can_retry is False
    
    def test_is_complete_property(self):
        """Test the is_complete property."""
        sent_step = EscalationStep(
            step_number=1,
            status=EscalationStatus.SENT,
            channel=EscalationChannel.EMAIL
        )
        
        acknowledged_step = EscalationStep(
            step_number=1,
            status=EscalationStatus.ACKNOWLEDGED,
            channel=EscalationChannel.SMS
        )
        
        pending_step = EscalationStep(
            step_number=1,
            status=EscalationStatus.PENDING,
            channel=EscalationChannel.EMAIL
        )
        
        assert sent_step.is_complete is True
        assert acknowledged_step.is_complete is True
        assert pending_step.is_complete is False