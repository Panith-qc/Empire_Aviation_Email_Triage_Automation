"""Activity log model for audit trail."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ActivityType(str, Enum):
    """Activity type enumeration."""
    
    # Email processing
    EMAIL_RECEIVED = "email_received"
    EMAIL_CLASSIFIED = "email_classified"
    EMAIL_PARSED = "email_parsed"
    
    # Ticket lifecycle
    TICKET_CREATED = "ticket_created"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    TICKET_UPDATED = "ticket_updated"
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_CLOSED = "ticket_closed"
    
    # Customer communication
    CONFIRMATION_SENT = "confirmation_sent"
    CUSTOMER_REPLY_RECEIVED = "customer_reply_received"
    
    # Escalation
    ESCALATION_STARTED = "escalation_started"
    ESCALATION_STEP_EXECUTED = "escalation_step_executed"
    ESCALATION_STOPPED = "escalation_stopped"
    SMS_SENT = "sms_sent"
    EMAIL_ESCALATION_SENT = "email_escalation_sent"
    
    # Internal communication
    INTERNAL_REPLY_RECEIVED = "internal_reply_received"
    ASSIGNMENT_ACKNOWLEDGED = "assignment_acknowledged"
    
    # System events
    SYSTEM_ERROR = "system_error"
    CLASSIFICATION_ERROR = "classification_error"
    COMMUNICATION_ERROR = "communication_error"


class ActivityLog(Base):
    """Activity log for audit trail."""
    
    __tablename__ = "activity_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # References
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        index=True
    )
    email_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        index=True
    )
    
    # Activity details
    activity_type: Mapped[ActivityType] = mapped_column(
        SQLEnum(ActivityType),
        index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Actor information
    actor_type: Mapped[str] = mapped_column(String(50))  # system, user, customer
    actor_id: Mapped[Optional[str]] = mapped_column(String(255))
    actor_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Additional context
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    # Success/error tracking
    is_success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
    
    # Relationships
    ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket",
        back_populates="activity_logs"
    )
    email_message: Mapped[Optional["EmailMessage"]] = relationship("EmailMessage")
    
    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, type='{self.activity_type}', title='{self.title}')>"