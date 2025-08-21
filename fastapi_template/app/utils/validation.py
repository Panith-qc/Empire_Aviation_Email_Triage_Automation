"""Input validation utilities."""

import re
from typing import Optional
from email_validator import validate_email as email_validate, EmailNotValidError


def validate_email(email: str) -> bool:
    """Validate email address format."""
    try:
        email_validate(email)
        return True
    except EmailNotValidError:
        return False


def validate_phone(phone: str) -> bool:
    """Validate phone number format (basic validation)."""
    # Remove common formatting characters
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Basic validation: starts with + or digit, 7-15 digits total
    pattern = r'^(\+?\d{7,15})$'
    return bool(re.match(pattern, cleaned))


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize input text by removing potentially harmful content."""
    if not text:
        return ""
    
    # Remove potential script tags and other HTML
    text = re.sub(r'<[^>]*>', '', text)
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()


def extract_aircraft_registration(text: str) -> Optional[str]:
    """Extract aircraft registration from text using common patterns."""
    # Common aircraft registration patterns
    patterns = [
        r'\b[A-Z]-[A-Z]{4}\b',  # International format (e.g., N-1234A)
        r'\b[A-Z]{1,2}-?[A-Z0-9]{3,5}\b',  # Various formats
        r'\bN\d{1,5}[A-Z]{0,2}\b',  # US format (e.g., N123AB)
        r'\b[A-Z]{2}-[A-Z0-9]{3,4}\b',  # European format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.upper())
        if match:
            return match.group(0)
    
    return None


def extract_phone_numbers(text: str) -> list[str]:
    """Extract phone numbers from text."""
    # Pattern for various phone number formats
    pattern = r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
    matches = re.findall(pattern, text)
    
    # Format found numbers
    phone_numbers = []
    for match in matches:
        formatted = f"({match[0]}) {match[1]}-{match[2]}"
        phone_numbers.append(formatted)
    
    return phone_numbers


def is_aog_keyword(text: str) -> bool:
    """Check if text contains AOG (Aircraft on Ground) keywords."""
    aog_keywords = [
        "aog", "aircraft on ground", "grounded", "stranded", "stuck",
        "emergency", "urgent", "critical", "immediate", "asap"
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in aog_keywords)


def is_maintenance_keyword(text: str) -> bool:
    """Check if text contains maintenance-related keywords."""
    maintenance_keywords = [
        "maintenance", "repair", "service", "inspection", "check",
        "fix", "broken", "malfunction", "issue", "problem",
        "engine", "hydraulic", "electrical", "avionics", "component"
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in maintenance_keywords)


def extract_priority_indicators(text: str) -> str:
    """Extract priority level from text based on keywords."""
    text_lower = text.lower()
    
    critical_keywords = ["critical", "emergency", "urgent", "aog", "grounded", "immediate"]
    high_keywords = ["high", "priority", "important", "asap", "soon"]
    
    if any(keyword in text_lower for keyword in critical_keywords):
        return "critical"
    elif any(keyword in text_lower for keyword in high_keywords):
        return "high"
    else:
        return "normal"


def clean_subject_line(subject: str) -> str:
    """Clean and normalize email subject line."""
    if not subject:
        return "No Subject"
    
    # Remove common prefixes
    prefixes = ["re:", "fwd:", "fw:", "forward:", "reply:"]
    subject_lower = subject.lower().strip()
    
    for prefix in prefixes:
        if subject_lower.startswith(prefix):
            subject = subject[len(prefix):].strip()
            break
    
    return sanitize_input(subject, max_length=200)