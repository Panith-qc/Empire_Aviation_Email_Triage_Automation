#!/usr/bin/env python3
"""
Quick Email Test - Simplified version for immediate testing
No real email connection required - processes sample aviation emails
"""

import csv
import os
import re
from datetime import datetime
from typing import Dict, List

class AviationEmailClassifier:
    """Aviation email classifier for testing."""
    
    def __init__(self):
        self.aog_keywords = ['aog', 'urgent', 'emergency', 'grounded', 'critical', 'immediate']
        self.aircraft_pattern = r'\b[NC]-?[A-Z0-9]{2,6}\b'
        
    def classify_email(self, subject: str, body: str, sender: str) -> Dict:
        """Classify aviation email."""
        text = (subject + ' ' + body).lower()
        
        # Extract aircraft registration
        aircraft = self._extract_aircraft(subject + ' ' + body)
        
        # Determine if AOG
        is_aog = any(keyword in text for keyword in self.aog_keywords)
        
        # Classify category
        if is_aog or 'emergency' in text:
            category = 'AOG'
            priority = 'CRITICAL'
            confidence = 0.95
        elif any(word in text for word in ['maintenance', 'service', 'repair']):
            category = 'MAINTENANCE'
            priority = 'HIGH' if 'urgent' in text else 'NORMAL'
            confidence = 0.85
        elif any(word in text for word in ['invoice', 'billing', 'payment']):
            category = 'INVOICE'
            priority = 'NORMAL'
            confidence = 0.90
        elif any(word in text for word in ['parts', 'delivery', 'component']):
            category = 'PARTS'
            priority = 'NORMAL'
            confidence = 0.80
        else:
            category = 'GENERAL'
            priority = 'NORMAL'
            confidence = 0.70
            
        return {
            'category': category,
            'priority': priority,
            'is_aog': is_aog,
            'aircraft_registration': aircraft,
            'confidence': confidence
        }
    
    def _extract_aircraft(self, text: str) -> str:
        """Extract aircraft registration."""
        matches = re.findall(self.aircraft_pattern, text.upper())
        return matches[0] if matches else None

def main():
    """Quick test with sample aviation emails."""
    
    print("🚁 EMBASSY AVIATION MAILBOT - QUICK EMAIL TEST")
    print("=" * 60)
    print("Testing with realistic aviation email samples...")
    print()
    
    # Realistic aviation email samples
    test_emails = [
        {
            'sender': 'dispatch@americanairlines.com',
            'subject': 'URGENT AOG - Aircraft N789XY engine failure at DFW',
            'body': 'Aircraft N789XY has experienced engine failure on taxiway. Flight AA1234 cancelled. Need immediate maintenance response. 150 passengers affected.'
        },
        {
            'sender': 'maintenance@united.com',
            'subject': 'Scheduled A-check for N456CD next week',
            'body': 'Please schedule A-check maintenance for aircraft N456CD. Aircraft available Tuesday-Thursday next week at SFO maintenance base.'
        },
        {
            'sender': 'billing@delta.com',
            'subject': 'Invoice #DL-2024-1234 for recent maintenance work',
            'body': 'Please find attached invoice #DL-2024-1234 for maintenance work performed on your fleet last month. Payment due within 30 days.'
        },
        {
            'sender': 'ops@southwest.com',
            'subject': 'CRITICAL - N999SW hydraulic failure at MDW',
            'body': 'Aircraft N999SW experiencing hydraulic system failure. Cannot depart gate 12. Flight WN5678 delayed indefinitely. AOG situation.'
        },
        {
            'sender': 'parts@jetblue.com',
            'subject': 'Parts delivery for N123JB - Engine components',
            'body': 'Confirming delivery of engine components for aircraft N123JB. Parts arrived at JFK maintenance facility this morning.'
        }
    ]
    
    classifier = AviationEmailClassifier()
    results = []
    
    print("📧 PROCESSING AVIATION EMAILS:")
    print("=" * 40)
    
    for i, email in enumerate(test_emails, 1):
        print(f"\nEmail {i}: {email['subject']}")
        print(f"From: {email['sender']}")
        
        result = classifier.classify_email(
            email['subject'],
            email['body'], 
            email['sender']
        )
        
        print(f"→ Category: {result['category']}")
        print(f"→ Priority: {result['priority']}")
        print(f"→ AOG Emergency: {'🚨 YES' if result['is_aog'] else '✅ NO'}")
        print(f"→ Aircraft: {result['aircraft_registration'] or 'Not detected'}")
        print(f"→ Confidence: {result['confidence']:.2f}")
        
        results.append({
            'email_num': i,
            'sender': email['sender'],
            'subject': email['subject'],
            'category': result['category'],
            'priority': result['priority'],
            'is_aog': result['is_aog'],
            'aircraft': result['aircraft_registration'] or 'N/A',
            'confidence': result['confidence']
        })
    
    # Generate CSV report
    os.makedirs('quick_test_data', exist_ok=True)
    report_file = f"quick_test_data/aviation_email_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n📊 PROCESSING SUMMARY:")
    print("=" * 30)
    aog_count = sum(1 for r in results if r['is_aog'])
    aircraft_count = len(set(r['aircraft'] for r in results if r['aircraft'] != 'N/A'))
    
    print(f"📧 Total Emails: {len(results)}")
    print(f"🚨 AOG Emergencies: {aog_count}")
    print(f"✈️  Aircraft Detected: {aircraft_count}")
    print(f"📄 Report Saved: {report_file}")
    
    print(f"\n✅ QUICK TEST COMPLETE!")
    print("Ready to test with your real email inbox!")
    print("Run: python email_inbox_processor.py")

if __name__ == "__main__":
    main()