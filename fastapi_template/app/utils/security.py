"""Security utilities for hashing, encryption, and token generation."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption key (should be stored securely in production)
ENCRYPTION_KEY = settings.SECRET_KEY.encode()[:32].ljust(32, b'0')
cipher_suite = Fernet(Fernet.generate_key())


def hash_content(content: str) -> str:
    """Generate SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def verify_content(content: str, content_hash: str) -> bool:
    """Verify content against its hash."""
    return hash_content(content) == content_hash


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a JWT token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except JWTError:
        return None


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data."""
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    return cipher_suite.decrypt(encrypted_data.encode()).decode()


def generate_secure_id(length: int = 32) -> str:
    """Generate a cryptographically secure random ID."""
    return secrets.token_urlsafe(length)


def sanitize_email(email: str) -> str:
    """Sanitize email address for logging (mask domain)."""
    if "@" not in email:
        return email
    
    local, domain = email.split("@", 1)
    
    # Mask local part if longer than 3 characters
    if len(local) > 3:
        local = local[:2] + "*" * (len(local) - 3) + local[-1]
    
    # Mask domain except TLD
    domain_parts = domain.split(".")
    if len(domain_parts) > 1:
        domain_parts[0] = domain_parts[0][:2] + "*" * max(0, len(domain_parts[0]) - 2)
        domain = ".".join(domain_parts)
    
    return f"{local}@{domain}"


def sanitize_phone(phone: str) -> str:
    """Sanitize phone number for logging."""
    if len(phone) <= 4:
        return phone
    
    return phone[:2] + "*" * (len(phone) - 4) + phone[-2:]


def mask_sensitive_data(data: Union[str, Dict[str, Any]], fields: Optional[list] = None) -> Union[str, Dict[str, Any]]:
    """Mask sensitive data for logging."""
    if fields is None:
        fields = ["password", "token", "secret", "key", "auth"]
    
    if isinstance(data, str):
        # Simple string masking
        return "*" * min(len(data), 8)
    
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if any(field in key.lower() for field in fields):
                masked_data[key] = "*" * min(len(str(value)), 8)
            elif isinstance(value, dict):
                masked_data[key] = mask_sensitive_data(value, fields)
            else:
                masked_data[key] = value
        return masked_data
    
    return data