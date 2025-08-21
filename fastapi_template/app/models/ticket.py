"""Ticket model for tracking service requests."""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TicketStatus(str, Enum):
    """Ticket status enumeration."""
    
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


class TicketPriority(str, Enum):
    """Ticket priority enumeration."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"  # AOG requests


class TicketCategory(str, Enum):
    """Ticket category enumeration."""
    
    AOG = "aog"  # Aircraft on Ground
    SERVICE = "service"
    MAINTENANCE = "maintenance"
    GENERAL = "general"
    INVOICE = "invoice"
    UNKNOWN = "unknown"


class Ticket(Base):
    """Ticket model for service requests."""
    
    __tablename__ = "tickets"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # Ticket identification
    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    
    # Email reference
    email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        index=True
    )
    
    # Ticket details
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[TicketCategory] = mapped_column(
        SQLEnum(TicketCategory),
        default=TicketCategory.UNKNOWN,
        index=True
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SQLEnum(TicketPriority),
        default=TicketPriority.NORMAL,
        index=True
    )
    status: Mapped[TicketStatus] = mapped_column(
        SQLEnum(TicketStatus),
        default=TicketStatus.NEW,
        index=True
    )
    
    # Customer information
    customer_email: Mapped[str] = mapped_column(String(255), index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Aircraft information (aviation specific)
    aircraft_registration: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    aircraft_type: Mapped[Optional[str]] = mapped_column(String(100))
    aircraft_location: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Assignment
    assigned_to_email: Mapped[Optional[str]] = mapped_column(String(255))
    assigned_to_name: Mapped[Optional[str]] = mapped_column(String(255))
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # SLA tracking
    response_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True
    )
    resolution_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True
    )
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Escalation tracking
    escalation_level: Mapped[int] = mapped_column(default=0)
    last_escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    escalation_stopped: Mapped[bool] = mapped_column(default=False)
    escalation_stopped_reason: Mapped[Optional[str]] = mapped_column(String(255))
    
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
    email_message: Mapped["EmailMessage"] = relationship("EmailMessage")
    activity_logs: Mapped[List["ActivityLog"]] = relationship(
        "ActivityLog",
        back_populates="ticket",
        cascade="all, delete-orphan"
    )
    escalation_steps: Mapped[List["EscalationStep"]] = relationship(
        "EscalationStep",
        back_populates="ticket",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, number='{self.ticket_number}', status='{self.status}')>"
    
    @property
    def is_overdue(self) -> bool:
        """Check if ticket is overdue based on response SLA."""
        if not self.response_due_at or self.first_response_at:
            return False
        return datetime.utcnow() > self.response_due_at
    
    @property
    def is_aog(self) -> bool:
        """Check if this is an Aircraft on Ground ticket."""
        return self.category == TicketCategory.AOG or self.priority == TicketPriority.CRITICAL