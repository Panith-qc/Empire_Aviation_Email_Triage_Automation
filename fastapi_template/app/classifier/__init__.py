"""Email classification components for Embassy Aviation Mailbot."""

from .rules_engine import RulesClassifier
from .ml_classifier import MLClassifier

__all__ = [
    "RulesClassifier",
    "MLClassifier",
]