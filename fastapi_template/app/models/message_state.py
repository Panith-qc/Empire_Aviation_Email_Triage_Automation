"""Message state tracking for idempotency."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ProcessingStatus(str, Enum):
    """Message processing status enumeration."""
    
    RECEIVED = "received"
    PARSING = "parsing"
    CLASSIFYING = "classifying"
    CREATING_TICKET = "creating_ticket"
    SENDING_CONFIRMATION = "sending_confirmation"
    SCHEDULING_ESCALATION = "scheduling_escalation"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MessageState(Base):
    """Message state tracking for idempotency and status."""
    
    __tablename__ = "message_states"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # Message identification
    message_id: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    graph_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Processing state
    status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.RECEIVED,
        index=True
    )
    
    # Progress tracking
    current_step: Mapped[Optional[str]] = mapped_column(String(100))
    progress_percentage: Mapped[int] = mapped_column(default=0)
    
    # Checksum for content verification
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA-256
    
    # Processing details
    processed_by: Mapped[Optional[str]] = mapped_column(String(100))  # worker/process ID
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Error handling
    error_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    retry_after: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Metadata
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
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
    
    def __repr__(self) -> str:
        return f"<MessageState(id={self.id}, message_id='{self.message_id}', status='{self.status}')>"
    
    @property
    def is_processing(self) -> bool:
        """Check if message is currently being processed."""
        return self.status in [
            ProcessingStatus.PARSING,
            ProcessingStatus.CLASSIFYING,
            ProcessingStatus.CREATING_TICKET,
            ProcessingStatus.SENDING_CONFIRMATION,
            ProcessingStatus.SCHEDULING_ESCALATION
        ]
    
    @property
    def is_complete(self) -> bool:
        """Check if message processing is complete."""
        return self.status in [
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
            ProcessingStatus.SKIPPED
        ]