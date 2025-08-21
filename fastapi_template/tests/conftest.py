"""Pytest configuration and fixtures."""

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from app.main import app
from app.models.database import Base
from app.config import settings


# Create test database engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_embassy_mailbot.db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Create a test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Create a test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return {
        "id": "test-graph-id-123",
        "internetMessageId": "test-message-id-123",
        "subject": "AOG - Aircraft N123AB grounded at LAX",
        "sender": {
            "emailAddress": {
                "address": "customer@airline.com",
                "name": "John Smith"
            }
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": "ops@embassy-aviation.com"
                }
            }
        ],
        "receivedDateTime": "2024-01-15T10:30:00Z",
        "body": {
            "content": "Aircraft N123AB is grounded at LAX due to hydraulic issue. Need immediate assistance.",
            "contentType": "Text"
        },
        "hasAttachments": False
    }


@pytest.fixture
def sample_classification():
    """Sample classification result for testing."""
    from app.classifier.rules_engine import ClassificationResult
    from app.models.ticket import TicketCategory, TicketPriority
    
    return ClassificationResult(
        category=TicketCategory.AOG,
        priority=TicketPriority.CRITICAL,
        confidence=0.95,
        matched_keywords=["aog", "grounded"],
        aircraft_registration="N123AB",
        is_aog=True,
        reasoning="Contains AOG keywords and aircraft registration"
    )