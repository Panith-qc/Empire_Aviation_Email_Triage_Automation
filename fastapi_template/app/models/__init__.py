"""Database models for Embassy Aviation Mailbot."""

from .database import Base, get_db_session
from .email import EmailMessage, EmailAttachment
from .ticket import Ticket, TicketStatus, TicketPriority
from .activity import ActivityLog, ActivityType
from .escalation import EscalationStep, EscalationStatus
from .message_state import MessageState, ProcessingStatus

__all__ = [
    "Base",
    "get_db_session",
    "EmailMessage",
    "EmailAttachment", 
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "ActivityLog",
    "ActivityType",
    "EscalationStep",
    "EscalationStatus",
    "MessageState",
    "ProcessingStatus",
]