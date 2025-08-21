"""Rules-based email classification engine."""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from app.models.ticket import TicketCategory, TicketPriority
from app.utils.logging import get_logger
from app.utils.validation import (
    is_aog_keyword,
    is_maintenance_keyword,
    extract_priority_indicators,
    extract_aircraft_registration
)

logger = get_logger(__name__)


@dataclass
class ClassificationResult:
    """Result of email classification."""
    category: TicketCategory
    priority: TicketPriority
    confidence: float
    matched_keywords: List[str]
    aircraft_registration: Optional[str] = None
    is_aog: bool = False
    reasoning: Optional[str] = None


class RulesClassifier:
    """Rules-based email classifier for aviation service requests."""
    
    def __init__(self, rules_file: Optional[str] = None):
        self.rules_file = rules_file or "app/classifier/rules.yaml"
        self.rules: Dict[str, Any] = {}
        self.load_rules()
    
    def load_rules(self) -> None:
        """Load classification rules from YAML file."""
        try:
            rules_path = Path(self.rules_file)
            if rules_path.exists():
                with open(rules_path, 'r', encoding='utf-8') as f:
                    self.rules = yaml.safe_load(f) or {}
                logger.info("Loaded classification rules", file=self.rules_file)
            else:
                logger.warning("Rules file not found, using defaults", file=self.rules_file)
                self.rules = self._get_default_rules()
                
        except Exception as e:
            logger.error("Error loading rules file", file=self.rules_file, error=str(e))
            self.rules = self._get_default_rules()
    
    def classify_email(
        self,
        subject: str,
        body: str,
        sender_email: str,
        attachments: Optional[List[str]] = None
    ) -> ClassificationResult:
        """Classify an email based on rules."""
        # Combine text for analysis
        text = f"{subject} {body}".lower()
        matched_keywords = []
        confidence = 0.0
        
        # Check for AOG keywords first (highest priority)
        aog_keywords = self.rules.get("aviation_keywords", {}).get("critical", [])
        aog_matches = [kw for kw in aog_keywords if kw.lower() in text]
        
        if aog_matches or is_aog_keyword(text):
            matched_keywords.extend(aog_matches)
            return ClassificationResult(
                category=TicketCategory.AOG,
                priority=TicketPriority.CRITICAL,
                confidence=0.95,
                matched_keywords=matched_keywords,
                aircraft_registration=extract_aircraft_registration(text),
                is_aog=True,
                reasoning="Contains AOG/critical aviation keywords"
            )
        
        # Check urgent keywords
        urgent_keywords = self.rules.get("aviation_keywords", {}).get("urgent", [])
        urgent_matches = [kw for kw in urgent_keywords if kw.lower() in text]
        
        if urgent_matches:
            matched_keywords.extend(urgent_matches)
            confidence += 0.3
        
        # Apply category rules
        category_scores = {}
        
        for rule in self.rules.get("categories", []):
            rule_name = rule.get("name", "unknown")
            rule_priority = rule.get("priority", "normal")
            conditions = rule.get("conditions", {})
            
            score = self._evaluate_rule_conditions(
                conditions, text, sender_email, attachments or []
            )
            
            if score > 0:
                category_scores[rule_name.lower()] = {
                    "score": score,
                    "priority": rule_priority,
                    "rule": rule
                }
        
        # Determine best category
        if not category_scores:
            # Fallback classification
            if is_maintenance_keyword(text):
                return ClassificationResult(
                    category=TicketCategory.SERVICE,
                    priority=TicketPriority.NORMAL,
                    confidence=0.6,
                    matched_keywords=["maintenance", "service"],
                    reasoning="Contains maintenance-related keywords"
                )
            else:
                return ClassificationResult(
                    category=TicketCategory.GENERAL,
                    priority=TicketPriority.NORMAL,
                    confidence=0.4,
                    matched_keywords=[],
                    reasoning="No specific category matched, defaulting to general"
                )
        
        # Get highest scoring category
        best_category = max(category_scores.items(), key=lambda x: x[1]["score"])
        category_name, category_data = best_category
        
        # Map category name to enum
        category_mapping = {
            "aog": TicketCategory.AOG,
            "service": TicketCategory.SERVICE,
            "maintenance": TicketCategory.MAINTENANCE,
            "general": TicketCategory.GENERAL,
            "invoice": TicketCategory.INVOICE
        }
        
        category = category_mapping.get(category_name, TicketCategory.GENERAL)
        
        # Map priority
        priority_mapping = {
            "low": TicketPriority.LOW,
            "normal": TicketPriority.NORMAL,
            "high": TicketPriority.HIGH,
            "critical": TicketPriority.CRITICAL
        }
        
        priority = priority_mapping.get(category_data["priority"], TicketPriority.NORMAL)
        
        # Adjust priority based on text analysis
        priority_from_text = extract_priority_indicators(text)
        if priority_from_text == "critical" and priority != TicketPriority.CRITICAL:
            priority = TicketPriority.HIGH  # Bump up but not to critical unless it's AOG
        
        # Calculate final confidence
        final_confidence = min(0.9, category_data["score"] + confidence)
        
        return ClassificationResult(
            category=category,
            priority=priority,
            confidence=final_confidence,
            matched_keywords=matched_keywords,
            aircraft_registration=extract_aircraft_registration(text),
            is_aog=(category == TicketCategory.AOG),
            reasoning=f"Matched rule: {category_name} (score: {category_data['score']:.2f})"
        )
    
    def _evaluate_rule_conditions(
        self,
        conditions: Dict[str, Any],
        text: str,
        sender_email: str,
        attachments: List[str]
    ) -> float:
        """Evaluate rule conditions and return confidence score."""
        total_score = 0.0
        max_possible_score = 0.0
        
        # Subject contains check
        if "subject_contains" in conditions:
            max_possible_score += 0.4
            keywords = conditions["subject_contains"]
            if isinstance(keywords, str):
                keywords = [keywords]
            
            matches = sum(1 for kw in keywords if kw.lower() in text)
            if matches > 0:
                total_score += 0.4 * (matches / len(keywords))
        
        # Body contains check
        if "body_contains" in conditions:
            max_possible_score += 0.3
            keywords = conditions["body_contains"]
            if isinstance(keywords, str):
                keywords = [keywords]
            
            matches = sum(1 for kw in keywords if kw.lower() in text)
            if matches > 0:
                total_score += 0.3 * (matches / len(keywords))
        
        # Sender domain check
        if "sender_domains" in conditions:
            max_possible_score += 0.2
            domains = conditions["sender_domains"]
            if isinstance(domains, str):
                domains = [domains]
            
            sender_domain = sender_email.split("@")[-1].lower() if "@" in sender_email else ""
            if any(domain.lower() in sender_domain for domain in domains):
                total_score += 0.2
        
        # Attachment check
        if "has_attachments" in conditions:
            max_possible_score += 0.1
            required = conditions["has_attachments"]
            if (required and attachments) or (not required and not attachments):
                total_score += 0.1
        
        # Return normalized score
        return total_score / max_possible_score if max_possible_score > 0 else 0.0
    
    def _get_default_rules(self) -> Dict[str, Any]:
        """Get default classification rules."""
        return {
            "version": 1,
            "aviation_keywords": {
                "critical": [
                    "aog", "aircraft on ground", "grounded", "emergency",
                    "critical", "urgent", "immediate", "stranded", "stuck"
                ],
                "urgent": [
                    "notam", "delay", "diverted", "mel", "weather",
                    "maintenance", "repair", "inspection", "service"
                ]
            },
            "categories": [
                {
                    "name": "AOG",
                    "priority": "critical",
                    "conditions": {
                        "subject_contains": ["aog", "aircraft on ground", "grounded", "emergency"],
                        "body_contains": ["aircraft", "grounded", "emergency", "critical"]
                    }
                },
                {
                    "name": "Service",
                    "priority": "high",
                    "conditions": {
                        "subject_contains": ["service", "maintenance", "repair", "inspection"],
                        "body_contains": ["service", "maintenance", "repair", "fix"]
                    }
                },
                {
                    "name": "Maintenance",
                    "priority": "high",
                    "conditions": {
                        "subject_contains": ["maintenance", "mx", "engine", "component"],
                        "body_contains": ["maintenance", "engine", "hydraulic", "electrical"]
                    }
                },
                {
                    "name": "General",
                    "priority": "normal",
                    "conditions": {
                        "subject_contains": ["inquiry", "question", "information"],
                        "body_contains": ["question", "information", "help"]
                    }
                },
                {
                    "name": "Invoice",
                    "priority": "normal",
                    "conditions": {
                        "subject_contains": ["invoice", "billing", "payment"],
                        "body_contains": ["invoice", "bill", "payment", "charge"]
                    }
                }
            ]
        }
    
    def update_rules(self, new_rules: Dict[str, Any]) -> bool:
        """Update classification rules."""
        try:
            # Validate rules structure
            if not self._validate_rules(new_rules):
                return False
            
            # Save to file
            rules_path = Path(self.rules_file)
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(rules_path, 'w', encoding='utf-8') as f:
                yaml.dump(new_rules, f, default_flow_style=False, allow_unicode=True)
            
            # Reload rules
            self.rules = new_rules
            logger.info("Updated classification rules", file=self.rules_file)
            return True
            
        except Exception as e:
            logger.error("Error updating rules", file=self.rules_file, error=str(e))
            return False
    
    def _validate_rules(self, rules: Dict[str, Any]) -> bool:
        """Validate rules structure."""
        try:
            # Check required fields
            if "categories" not in rules:
                logger.error("Rules validation failed: missing 'categories'")
                return False
            
            # Validate each category
            for category in rules["categories"]:
                if "name" not in category:
                    logger.error("Rules validation failed: category missing 'name'")
                    return False
                
                if "conditions" not in category:
                    logger.error("Rules validation failed: category missing 'conditions'")
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Error validating rules", error=str(e))
            return False
    
    def get_category_stats(self) -> Dict[str, int]:
        """Get statistics about rule categories."""
        stats = {}
        for category in self.rules.get("categories", []):
            name = category.get("name", "unknown")
            stats[name] = len(category.get("conditions", {}))
        return stats