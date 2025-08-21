"""Contact management for escalations."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import settings
from app.models.ticket import TicketCategory, TicketPriority
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ContactManager:
    """Manages escalation contacts and routing rules."""
    
    def __init__(self, contacts_file: Optional[str] = None):
        self.contacts_file = contacts_file or "app/escalation/contacts.json"
        self.contacts: Dict[str, Any] = {}
        self.load_contacts()
    
    def load_contacts(self) -> None:
        """Load escalation contacts from JSON file."""
        try:
            contacts_path = Path(self.contacts_file)
            if contacts_path.exists():
                with open(contacts_path, 'r', encoding='utf-8') as f:
                    self.contacts = json.load(f)
                logger.info("Loaded escalation contacts", file=self.contacts_file)
            else:
                logger.warning("Contacts file not found, using defaults", file=self.contacts_file)
                self.contacts = self._get_default_contacts()
                
        except Exception as e:
            logger.error("Error loading contacts file", file=self.contacts_file, error=str(e))
            self.contacts = self._get_default_contacts()
    
    async def get_escalation_contacts(
        self,
        category: TicketCategory,
        priority: TicketPriority
    ) -> List[Dict[str, Any]]:
        """Get escalation contacts for a ticket category and priority."""
        try:
            # Get category-specific contacts
            category_key = category.value.lower()
            category_contacts = self.contacts.get("categories", {}).get(category_key, {})
            
            # Get priority-specific routing
            priority_key = priority.value.lower()
            priority_contacts = category_contacts.get("contacts", {}).get(priority_key, [])
            
            # If no priority-specific contacts, use default for category
            if not priority_contacts:
                priority_contacts = category_contacts.get("contacts", {}).get("default", [])
            
            # If still no contacts, use global defaults
            if not priority_contacts:
                priority_contacts = self.contacts.get("global", {}).get("default", [])
            
            # Resolve contact references
            resolved_contacts = []
            for contact_ref in priority_contacts:
                if isinstance(contact_ref, str):
                    # Reference to named contact
                    contact = self._resolve_contact_reference(contact_ref)
                    if contact:
                        resolved_contacts.append(contact)
                elif isinstance(contact_ref, dict):
                    # Inline contact definition
                    resolved_contacts.append(contact_ref)
            
            # Add global emergency contacts for critical tickets
            if priority == TicketPriority.CRITICAL:
                emergency_contacts = self.contacts.get("emergency", [])
                for contact_ref in emergency_contacts:
                    contact = self._resolve_contact_reference(contact_ref)
                    if contact and contact not in resolved_contacts:
                        resolved_contacts.append(contact)
            
            logger.info("Retrieved escalation contacts",
                       category=category.value,
                       priority=priority.value,
                       contact_count=len(resolved_contacts))
            
            return resolved_contacts
            
        except Exception as e:
            logger.error("Error getting escalation contacts",
                        category=category.value,
                        priority=priority.value,
                        error=str(e))
            return []
    
    def _resolve_contact_reference(self, contact_ref: str) -> Optional[Dict[str, Any]]:
        """Resolve a contact reference to actual contact details."""
        try:
            # Look in named contacts
            named_contacts = self.contacts.get("named_contacts", {})
            contact = named_contacts.get(contact_ref)
            
            if contact:
                return contact.copy()
            
            # Look in environment variables for emails/phones
            if contact_ref == "internal_emails":
                emails = settings.ESCALATION_INTERNAL_EMAILS
                if emails:
                    return {
                        "name": "Internal Team",
                        "email": emails[0],  # Use first email
                        "role": "operations"
                    }
            
            elif contact_ref == "internal_numbers":
                numbers = settings.ESCALATION_INTERNAL_NUMBERS
                if numbers:
                    return {
                        "name": "Internal Team",
                        "phone": numbers[0],  # Use first number
                        "role": "operations"
                    }
            
            logger.warning("Contact reference not found", reference=contact_ref)
            return None
            
        except Exception as e:
            logger.error("Error resolving contact reference",
                        reference=contact_ref,
                        error=str(e))
            return None
    
    def _get_default_contacts(self) -> Dict[str, Any]:
        """Get default contact configuration."""
        return {
            "version": 1,
            "named_contacts": {
                "ops_manager": {
                    "name": "Operations Manager",
                    "email": "ops-manager@embassy-aviation.com",
                    "phone": "+1234567890",
                    "role": "operations_manager"
                },
                "maintenance_lead": {
                    "name": "Maintenance Lead",
                    "email": "maintenance-lead@embassy-aviation.com", 
                    "phone": "+1234567891",
                    "role": "maintenance_lead"
                },
                "customer_service": {
                    "name": "Customer Service",
                    "email": "service@embassy-aviation.com",
                    "phone": "+1234567892",
                    "role": "customer_service"
                },
                "director": {
                    "name": "Director of Operations",
                    "email": "director@embassy-aviation.com",
                    "phone": "+1234567893",
                    "role": "director"
                }
            },
            "categories": {
                "aog": {
                    "description": "Aircraft on Ground - Critical situations",
                    "contacts": {
                        "critical": ["ops_manager", "maintenance_lead", "director"],
                        "default": ["ops_manager", "maintenance_lead"]
                    }
                },
                "service": {
                    "description": "General service requests",
                    "contacts": {
                        "high": ["maintenance_lead", "ops_manager"],
                        "normal": ["maintenance_lead"],
                        "default": ["maintenance_lead"]
                    }
                },
                "maintenance": {
                    "description": "Maintenance requests",
                    "contacts": {
                        "high": ["maintenance_lead", "ops_manager"],
                        "normal": ["maintenance_lead"],
                        "default": ["maintenance_lead"]
                    }
                },
                "general": {
                    "description": "General inquiries",
                    "contacts": {
                        "normal": ["customer_service"],
                        "default": ["customer_service"]
                    }
                },
                "invoice": {
                    "description": "Billing and invoice inquiries",
                    "contacts": {
                        "normal": ["customer_service"],
                        "default": ["customer_service"]
                    }
                }
            },
            "emergency": ["ops_manager", "director"],
            "global": {
                "default": ["customer_service"]
            }
        }
    
    def update_contacts(self, new_contacts: Dict[str, Any]) -> bool:
        """Update contact configuration."""
        try:
            # Validate structure
            if not self._validate_contacts(new_contacts):
                return False
            
            # Save to file
            contacts_path = Path(self.contacts_file)
            contacts_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(contacts_path, 'w', encoding='utf-8') as f:
                json.dump(new_contacts, f, indent=2)
            
            # Reload contacts
            self.contacts = new_contacts
            logger.info("Updated escalation contacts", file=self.contacts_file)
            return True
            
        except Exception as e:
            logger.error("Error updating contacts", file=self.contacts_file, error=str(e))
            return False
    
    def _validate_contacts(self, contacts: Dict[str, Any]) -> bool:
        """Validate contact configuration structure."""
        try:
            # Check required fields
            if "named_contacts" not in contacts:
                logger.error("Contacts validation failed: missing 'named_contacts'")
                return False
            
            if "categories" not in contacts:
                logger.error("Contacts validation failed: missing 'categories'")
                return False
            
            # Validate named contacts
            for name, contact in contacts["named_contacts"].items():
                if not isinstance(contact, dict):
                    logger.error(f"Invalid contact definition: {name}")
                    return False
                
                if "name" not in contact:
                    logger.error(f"Contact missing name: {name}")
                    return False
                
                if not contact.get("email") and not contact.get("phone"):
                    logger.error(f"Contact missing email and phone: {name}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Error validating contacts", error=str(e))
            return False
    
    def get_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get contact information by email address."""
        for contact in self.contacts.get("named_contacts", {}).values():
            if contact.get("email", "").lower() == email.lower():
                return contact
        return None
    
    def get_contact_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get contact information by phone number."""
        # Normalize phone numbers for comparison
        normalized_phone = ''.join(filter(str.isdigit, phone))
        
        for contact in self.contacts.get("named_contacts", {}).values():
            contact_phone = contact.get("phone", "")
            normalized_contact_phone = ''.join(filter(str.isdigit, contact_phone))
            
            if normalized_contact_phone and normalized_contact_phone == normalized_phone:
                return contact
        return None
    
    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Get all named contacts."""
        return list(self.contacts.get("named_contacts", {}).values())
    
    def get_contacts_summary(self) -> Dict[str, Any]:
        """Get summary of contact configuration."""
        named_contacts = self.contacts.get("named_contacts", {})
        categories = self.contacts.get("categories", {})
        
        return {
            "total_named_contacts": len(named_contacts),
            "categories": list(categories.keys()),
            "contacts_with_email": len([c for c in named_contacts.values() if c.get("email")]),
            "contacts_with_phone": len([c for c in named_contacts.values() if c.get("phone")]),
            "emergency_contacts": len(self.contacts.get("emergency", []))
        }