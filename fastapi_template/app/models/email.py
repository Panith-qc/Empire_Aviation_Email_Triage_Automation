"""Email message and attachment models."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EmailMessage(Base):
    """Email message model."""
    
    __tablename__ = "email_messages"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # Graph/IMAP identifiers
    message_id: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    graph_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Email headers
    subject: Mapped[str] = mapped_column(String(500), index=True)
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255))
    recipient_emails: Mapped[str] = mapped_column(Text)  # JSON array as string
    cc_emails: Mapped[Optional[str]] = mapped_column(Text)  # JSON array as string
    bcc_emails: Mapped[Optional[str]] = mapped_column(Text)  # JSON array as string
    
    # Email content
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    mailbox: Mapped[str] = mapped_column(String(255), index=True)
    folder_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(default=False, index=True)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    
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
    attachments: Mapped[List["EmailAttachment"]] = relationship(
        "EmailAttachment",
        back_populates="email_message",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<EmailMessage(id={self.id}, subject='{self.subject[:50]}...')>"


class EmailAttachment(Base):
    """Email attachment model."""
    
    __tablename__ = "email_attachments"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    email_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        index=True
    )
    
    # Attachment metadata
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    
    # Storage information
    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA-256
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    # Relationships
    email_message: Mapped["EmailMessage"] = relationship(
        "EmailMessage",
        back_populates="attachments"
    )
    
    def __repr__(self) -> str:
        return f"<EmailAttachment(id={self.id}, filename='{self.filename}')>"