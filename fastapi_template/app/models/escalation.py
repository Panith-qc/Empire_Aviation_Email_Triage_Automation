"""Escalation models for tracking escalation steps."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EscalationStatus(str, Enum):
    """Escalation status enumeration."""
    
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"
    SKIPPED = "skipped"


class EscalationChannel(str, Enum):
    """Escalation channel enumeration."""
    
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"
    TEAMS = "teams"
    SLACK = "slack"


class EscalationStep(Base):
    """Escalation step model."""
    
    __tablename__ = "escalation_steps"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # References
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        index=True
    )
    
    # Escalation details
    step_number: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[EscalationStatus] = mapped_column(
        SQLEnum(EscalationStatus),
        default=EscalationStatus.PENDING,
        index=True
    )
    channel: Mapped[EscalationChannel] = mapped_column(SQLEnum(EscalationChannel))
    
    # Contact information
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    contact_role: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Message details
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    message_body: Mapped[Optional[str]] = mapped_column(Text)
    message_id: Mapped[Optional[str]] = mapped_column(String(255))  # External message ID
    
    # Error handling
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    ticket: Mapped["Ticket"] = relationship(
        "Ticket",
        back_populates="escalation_steps"
    )
    
    def __repr__(self) -> str:
        return f"<EscalationStep(id={self.id}, step={self.step_number}, status='{self.status}')>"
    
    @property
    def can_retry(self) -> bool:
        """Check if this step can be retried."""
        return (
            self.status == EscalationStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    @property
    def is_complete(self) -> bool:
        """Check if this escalation step is complete."""
        return self.status in [
            EscalationStatus.SENT,
            EscalationStatus.ACKNOWLEDGED,
            EscalationStatus.SKIPPED
        ]