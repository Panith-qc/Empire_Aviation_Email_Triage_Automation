"""Structured logging configuration using structlog."""

import logging
import sys
import uuid
from typing import Any, Dict, Optional

import structlog
from structlog.types import FilteringBoundLogger

from app.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.CallsiteParameterAdder(
                parameters={
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    
    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> FilteringBoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name or __name__)


class CorrelationContextManager:
    """Context manager for correlation ID tracking."""
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.token = None
    
    def __enter__(self):
        self.token = structlog.contextvars.bind_contextvars(
            correlation_id=self.correlation_id
        )
        return self.correlation_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            structlog.contextvars.unbind_contextvars("correlation_id")


def log_email_processing(
    logger: FilteringBoundLogger,
    email_id: str,
    message_id: str,
    step: str,
    **kwargs: Any
) -> None:
    """Log email processing steps with consistent format."""
    logger.info(
        f"Email processing: {step}",
        email_id=email_id,
        message_id=message_id,
        step=step,
        **kwargs
    )


def log_escalation_event(
    logger: FilteringBoundLogger,
    ticket_id: str,
    step_number: int,
    channel: str,
    status: str,
    **kwargs: Any
) -> None:
    """Log escalation events with consistent format."""
    logger.info(
        f"Escalation {status}: Step {step_number} via {channel}",
        ticket_id=ticket_id,
        escalation_step=step_number,
        escalation_channel=channel,
        escalation_status=status,
        **kwargs
    )


def log_api_request(
    logger: FilteringBoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **kwargs: Any
) -> None:
    """Log API requests with consistent format."""
    logger.info(
        f"{method} {path} - {status_code}",
        http_method=method,
        http_path=path,
        http_status=status_code,
        duration_ms=duration_ms,
        **kwargs
    )


def log_external_api_call(
    logger: FilteringBoundLogger,
    service: str,
    operation: str,
    success: bool,
    duration_ms: float,
    **kwargs: Any
) -> None:
    """Log external API calls with consistent format."""
    level = "info" if success else "error"
    getattr(logger, level)(
        f"{service} API call: {operation}",
        external_service=service,
        operation=operation,
        success=success,
        duration_ms=duration_ms,
        **kwargs
    )