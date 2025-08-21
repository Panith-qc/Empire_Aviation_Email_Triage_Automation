"""Machine learning-based email classifier (optional enhancement)."""

import pickle
from pathlib import Path
from typing import Optional, List, Dict, Any
import re

from app.models.ticket import TicketCategory, TicketPriority
from app.utils.logging import get_logger
from app.classifier.rules_engine import ClassificationResult

logger = get_logger(__name__)


class MLClassifier:
    """Machine learning classifier for email content (placeholder for future ML implementation)."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "app/classifier/models/email_classifier.pkl"
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.is_trained = False
        
    def load_model(self) -> bool:
        """Load trained ML model from disk."""
        try:
            model_file = Path(self.model_path)
            if not model_file.exists():
                logger.warning("ML model file not found", path=self.model_path)
                return False
            
            with open(model_file, 'rb') as f:
                model_data = pickle.load(f)
                self.model = model_data.get('model')
                self.vectorizer = model_data.get('vectorizer')
                self.label_encoder = model_data.get('label_encoder')
            
            self.is_trained = True
            logger.info("ML model loaded successfully", path=self.model_path)
            return True
            
        except Exception as e:
            logger.error("Error loading ML model", path=self.model_path, error=str(e))
            return False
    
    def classify_email(
        self,
        subject: str,
        body: str,
        sender_email: str,
        attachments: Optional[List[str]] = None
    ) -> Optional[ClassificationResult]:
        """Classify email using ML model."""
        if not self.is_trained:
            logger.warning("ML model not trained/loaded, skipping ML classification")
            return None
        
        try:
            # Prepare features
            features = self._extract_features(subject, body, sender_email, attachments or [])
            
            # Vectorize text
            text_features = self.vectorizer.transform([features['text']])
            
            # Predict category and confidence
            prediction = self.model.predict(text_features)[0]
            confidence_scores = self.model.predict_proba(text_features)[0]
            confidence = max(confidence_scores)
            
            # Decode prediction
            category_name = self.label_encoder.inverse_transform([prediction])[0]
            
            # Map to enums
            category_mapping = {
                'aog': TicketCategory.AOG,
                'service': TicketCategory.SERVICE,
                'maintenance': TicketCategory.MAINTENANCE,
                'general': TicketCategory.GENERAL,
                'invoice': TicketCategory.INVOICE
            }
            
            category = category_mapping.get(category_name.lower(), TicketCategory.GENERAL)
            
            # Determine priority based on category and confidence
            if category == TicketCategory.AOG:
                priority = TicketPriority.CRITICAL
            elif confidence > 0.8 and category in [TicketCategory.SERVICE, TicketCategory.MAINTENANCE]:
                priority = TicketPriority.HIGH
            else:
                priority = TicketPriority.NORMAL
            
            return ClassificationResult(
                category=category,
                priority=priority,
                confidence=confidence,
                matched_keywords=features['keywords'],
                aircraft_registration=features.get('aircraft_registration'),
                is_aog=(category == TicketCategory.AOG),
                reasoning=f"ML prediction: {category_name} (confidence: {confidence:.2f})"
            )
            
        except Exception as e:
            logger.error("Error in ML classification", error=str(e))
            return None
    
    def _extract_features(
        self,
        subject: str,
        body: str,
        sender_email: str,
        attachments: List[str]
    ) -> Dict[str, Any]:
        """Extract features for ML classification."""
        # Combine text
        full_text = f"{subject} {body}".lower()
        
        # Extract keywords
        aviation_keywords = [
            'aog', 'aircraft', 'grounded', 'maintenance', 'service',
            'repair', 'inspection', 'engine', 'hydraulic', 'electrical',
            'avionics', 'component', 'emergency', 'urgent', 'critical'
        ]
        
        found_keywords = [kw for kw in aviation_keywords if kw in full_text]
        
        # Extract aircraft registration
        aircraft_patterns = [
            r'\b[A-Z]-[A-Z]{4}\b',
            r'\b[A-Z]{1,2}-?[A-Z0-9]{3,5}\b',
            r'\bN\d{1,5}[A-Z]{0,2}\b'
        ]
        
        aircraft_registration = None
        for pattern in aircraft_patterns:
            match = re.search(pattern, full_text.upper())
            if match:
                aircraft_registration = match.group(0)
                break
        
        # Sender domain
        sender_domain = sender_email.split('@')[-1] if '@' in sender_email else ''
        
        return {
            'text': full_text,
            'keywords': found_keywords,
            'aircraft_registration': aircraft_registration,
            'sender_domain': sender_domain,
            'has_attachments': len(attachments) > 0,
            'attachment_count': len(attachments),
            'text_length': len(full_text),
            'keyword_count': len(found_keywords)
        }
    
    def train_model(self, training_data: List[Dict[str, Any]]) -> bool:
        """Train ML model with provided data (placeholder for future implementation)."""
        logger.warning("ML model training not implemented yet")
        return False
    
    def save_model(self) -> bool:
        """Save trained model to disk."""
        if not self.is_trained:
            logger.error("Cannot save untrained model")
            return False
        
        try:
            model_file = Path(self.model_path)
            model_file.parent.mkdir(parents=True, exist_ok=True)
            
            model_data = {
                'model': self.model,
                'vectorizer': self.vectorizer,
                'label_encoder': self.label_encoder
            }
            
            with open(model_file, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info("ML model saved successfully", path=self.model_path)
            return True
            
        except Exception as e:  
            logger.error("Error saving ML model", path=self.model_path, error=str(e))
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            'is_trained': self.is_trained,
            'model_path': self.model_path,
            'model_type': type(self.model).__name__ if self.model else None,
            'has_vectorizer': self.vectorizer is not None,
            'has_label_encoder': self.label_encoder is not None
        }