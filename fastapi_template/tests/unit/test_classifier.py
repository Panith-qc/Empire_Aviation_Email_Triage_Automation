"""Unit tests for email classification."""

import pytest
from app.classifier.rules_engine import RulesClassifier
from app.models.ticket import TicketCategory, TicketPriority


class TestRulesClassifier:
    """Test the rules-based email classifier."""
    
    def setup_method(self):
        """Set up test classifier."""
        self.classifier = RulesClassifier()
    
    def test_aog_classification(self):
        """Test AOG email classification."""
        subject = "AOG - Aircraft N123AB grounded at LAX"
        body = "Aircraft is grounded due to hydraulic failure. Need immediate assistance."
        sender = "customer@airline.com"
        
        result = self.classifier.classify_email(subject, body, sender)
        
        assert result.category == TicketCategory.AOG
        assert result.priority == TicketPriority.CRITICAL
        assert result.is_aog is True
        assert result.confidence > 0.9
        assert "aog" in [kw.lower() for kw in result.matched_keywords]
    
    def test_service_classification(self):
        """Test service request classification."""
        subject = "Maintenance request for scheduled inspection" 
        body = "Need to schedule 100-hour inspection for aircraft N456CD"
        sender = "maintenance@airline.com"
        
        result = self.classifier.classify_email(subject, body, sender)
        
        assert result.category in [TicketCategory.SERVICE, TicketCategory.MAINTENANCE]
        assert result.priority in [TicketPriority.HIGH, TicketPriority.NORMAL]
        assert result.is_aog is False
        assert result.confidence > 0.6
    
    def test_general_inquiry_classification(self):
        """Test general inquiry classification."""
        subject = "Question about invoice #12345"
        body = "I have a question about the charges on invoice #12345"
        sender = "billing@airline.com"
        
        result = self.classifier.classify_email(subject, body, sender)
        
        assert result.category in [TicketCategory.GENERAL, TicketCategory.INVOICE]
        assert result.priority == TicketPriority.NORMAL
        assert result.is_aog is False
    
    def test_aircraft_registration_extraction(self):
        """Test aircraft registration extraction."""
        subject = "Service request for N789EF"
        body = "Aircraft N789EF needs maintenance at KJFK"
        sender = "ops@airline.com"
        
        result = self.classifier.classify_email(subject, body, sender)
        
        assert result.aircraft_registration == "N789EF"
    
    def test_confidence_scoring(self):
        """Test confidence scoring mechanism."""
        # High confidence AOG
        result1 = self.classifier.classify_email(
            "URGENT AOG - Aircraft grounded",
            "Emergency situation, aircraft is grounded and needs immediate attention",
            "ops@airline.com"
        )
        
        # Low confidence general
        result2 = self.classifier.classify_email(
            "Hello",
            "Just saying hello",
            "someone@example.com"
        )
        
        assert result1.confidence > result2.confidence
        assert result1.confidence > 0.8
        assert result2.confidence < 0.6
    
    def test_priority_keywords(self):
        """Test priority keyword detection."""
        # Critical priority keywords
        result1 = self.classifier.classify_email(
            "EMERGENCY maintenance needed",
            "This is an emergency situation requiring immediate attention",
            "ops@airline.com"
        )
        
        # Normal priority
        result2 = self.classifier.classify_email(
            "Scheduled maintenance",
            "Please schedule routine maintenance when convenient",
            "planning@airline.com"
        )
        
        assert result1.priority in [TicketPriority.CRITICAL, TicketPriority.HIGH]
        assert result2.priority in [TicketPriority.NORMAL, TicketPriority.LOW]