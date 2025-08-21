#!/usr/bin/env python3
"""
Embassy Aviation Mailbot - Standalone Demo
Simple email triage system with CSV reports - NO DEPENDENCIES REQUIRED
"""

import csv
import re
import os
from datetime import datetime
from typing import Dict, List, Tuple

class AviationEmailClassifier:
    """Simple aviation email classifier."""
    
    def __init__(self):
        # Aviation-specific keywords
        self.aog_keywords = ['aog', 'urgent', 'emergency', 'grounded', 'critical', 'immediate']
        self.aircraft_pattern = r'\b[NC]-?[A-Z0-9]{2,6}\b'
        
    def classify_email(self, subject: str, body: str, sender: str) -> Dict:
        """Classify aviation email."""
        text = (subject + ' ' + body).lower()
        
        # Extract aircraft registration
        aircraft = self._extract_aircraft(subject + ' ' + body)
        
        # Determine if AOG (Aircraft on Ground)
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
        """Extract aircraft registration (tail number)."""
        matches = re.findall(self.aircraft_pattern, text.upper())
        return matches[0] if matches else None

class CSVReportGenerator:
    """Generate CSV reports for aviation email processing."""
    
    def __init__(self, data_dir: str = "aviation_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def process_and_save_emails(self, emails: List[Dict]) -> Dict:
        """Process emails and save to CSV files."""
        
        # File paths
        emails_file = os.path.join(self.data_dir, "processed_emails.csv")
        tickets_file = os.path.join(self.data_dir, "support_tickets.csv")
        summary_file = os.path.join(self.data_dir, "processing_summary.csv")
        
        classifier = AviationEmailClassifier()
        processed_results = []
        
        print("🚁 EMBASSY AVIATION EMAIL PROCESSING")
        print("=" * 50)
        
        # Process each email
        for i, email in enumerate(emails, 1):
            print(f"\n📧 Processing Email {i}/{len(emails)}")
            print(f"Subject: {email['subject']}")
            
            # Classify email
            result = classifier.classify_email(
                email['subject'], 
                email['body'], 
                email['sender']
            )
            
            # Create processed record
            processed_email = {
                'email_id': f"EMB-{datetime.now().strftime('%Y%m%d')}-{i:03d}",
                'ticket_number': f"TICKET-{i:03d}",
                'timestamp': datetime.now().isoformat(),
                'sender': email['sender'],
                'subject': email['subject'],
                'body': email['body'],
                'category': result['category'],
                'priority': result['priority'],
                'is_aog': result['is_aog'],
                'aircraft_registration': result['aircraft_registration'] or 'N/A',
                'confidence': result['confidence'],
                'status': 'PROCESSED'
            }
            
            processed_results.append(processed_email)
            
            # Print classification results
            print(f"→ Category: {result['category']}")
            print(f"→ Priority: {result['priority']}")
            print(f"→ AOG Emergency: {'🚨 YES' if result['is_aog'] else '✅ NO'}")
            print(f"→ Aircraft: {result['aircraft_registration'] or 'Not detected'}")
            print(f"→ Confidence: {result['confidence']:.2f}")
        
        # Save processed emails to CSV
        self._save_emails_csv(emails_file, processed_results)
        
        # Generate support tickets CSV
        self._save_tickets_csv(tickets_file, processed_results)
        
        # Generate summary report
        summary_stats = self._generate_summary_stats(processed_results)
        self._save_summary_csv(summary_file, summary_stats)
        
        print(f"\n📊 PROCESSING COMPLETE!")
        print(f"=" * 50)
        print(f"✅ Processed {len(processed_results)} emails")
        print(f"✅ Files saved to '{self.data_dir}/' directory")
        print(f"📧 processed_emails.csv - All email data")
        print(f"🎫 support_tickets.csv - Ticket information")  
        print(f"📈 processing_summary.csv - Statistics report")
        
        return summary_stats
    
    def _save_emails_csv(self, filepath: str, emails: List[Dict]):
        """Save processed emails to CSV."""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            if emails:
                writer = csv.DictWriter(f, fieldnames=emails[0].keys())
                writer.writeheader()
                writer.writerows(emails)
    
    def _save_tickets_csv(self, filepath: str, emails: List[Dict]):
        """Save support tickets to CSV."""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Ticket Number', 'Category', 'Priority', 'AOG Emergency',
                'Aircraft Registration', 'Customer Email', 'Subject',
                'Created Date', 'Status'
            ])
            
            for email in emails:
                writer.writerow([
                    email['ticket_number'],
                    email['category'],
                    email['priority'],
                    'YES' if email['is_aog'] else 'NO',
                    email['aircraft_registration'],
                    email['sender'],
                    email['subject'],
                    email['timestamp'][:10],
                    email['status']
                ])
    
    def _save_summary_csv(self, filepath: str, stats: Dict):
        """Save summary statistics to CSV."""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Emails Processed', stats['total_emails']])
            writer.writerow(['AOG Emergencies', stats['aog_count']])
            writer.writerow(['Aircraft Registrations Found', stats['aircraft_count']])
            writer.writerow(['Report Generated', stats['report_date']])
            writer.writerow(['', ''])
            writer.writerow(['Category Breakdown', 'Count'])
            
            for category, count in stats['categories'].items():
                writer.writerow([category, count])
            
            writer.writerow(['', ''])
            writer.writerow(['Priority Breakdown', 'Count'])
            for priority, count in stats['priorities'].items():
                writer.writerow([priority, count])
    
    def _generate_summary_stats(self, emails: List[Dict]) -> Dict:
        """Generate processing statistics."""
        categories = {}
        priorities = {}
        aog_count = 0
        aircraft_found = set()
        
        for email in emails:
            # Count categories
            cat = email['category']
            categories[cat] = categories.get(cat, 0) + 1
            
            # Count priorities
            pri = email['priority']
            priorities[pri] = priorities.get(pri, 0) + 1
            
            # Count AOG
            if email['is_aog']:
                aog_count += 1
            
            # Collect aircraft
            if email['aircraft_registration'] != 'N/A':
                aircraft_found.add(email['aircraft_registration'])
        
        return {
            'total_emails': len(emails),
            'aog_count': aog_count,
            'aircraft_count': len(aircraft_found),
            'categories': categories,
            'priorities': priorities,
            'report_date': datetime.now().isoformat()
        }

def main():
    """Main demonstration function."""
    
    print("🚁 EMBASSY AVIATION MAILBOT - STANDALONE DEMO")
    print("=" * 60)
    print("Processing aviation emails and generating CSV reports...")
    print()
    
    # Sample aviation emails for demonstration
    sample_emails = [
        {
            'sender': 'ops@americanairlines.com',
            'subject': 'URGENT AOG - Aircraft N789XY grounded at JFK Terminal 8',
            'body': 'Aircraft N789XY is currently grounded at JFK due to engine failure. Passengers have been deplaned. We need immediate maintenance assistance for this AOG situation. Flight AA1234 is delayed indefinitely.'
        },
        {
            'sender': 'maintenance@deltaair.com', 
            'subject': 'EMERGENCY - N123AB hydraulic system complete failure',
            'body': 'Aircraft N123AB experiencing total hydraulic system failure at LAX Gate 42. This is an AOG emergency requiring immediate attention. Flight DL5678 cannot depart until resolved.'
        },
        {
            'sender': 'scheduling@unitedairlines.com',
            'subject': 'Scheduled maintenance request for N456CD - 100 hour inspection',
            'body': 'Please schedule the required 100-hour inspection for aircraft N456CD. Aircraft is available next week. This is routine maintenance, not urgent.'
        },
        {
            'sender': 'billing@southwestair.com',
            'subject': 'Invoice inquiry regarding maintenance charges #INV-SW-12345',
            'body': 'We have questions about the recent invoice #INV-SW-12345 for maintenance work performed on our fleet. Please provide detailed breakdown of charges.'
        },
        {
            'sender': 'parts@jetblue.com',
            'subject': 'Parts delivery confirmation - Hydraulic components for N999EF',
            'body': 'Confirming delivery of hydraulic pump and related components for aircraft N999EF. Parts arrived at maintenance facility and are ready for installation.'
        },
        {
            'sender': 'emergency@alaskaair.com',
            'subject': 'CRITICAL AOG - N777AS tire blowout on landing at SEA',
            'body': 'Aircraft N777AS experienced tire blowout during landing at Seattle-Tacoma Airport. Aircraft is stuck on runway. This is a critical AOG situation requiring immediate response.'
        }
    ]
    
    # Initialize report generator
    report_gen = CSVReportGenerator()
    
    # Process emails and generate reports
    summary_stats = report_gen.process_and_save_emails(sample_emails)
    
    # Display final statistics
    print(f"\n📈 FINAL STATISTICS SUMMARY")
    print(f"=" * 50)
    print(f"🎯 Total Emails: {summary_stats['total_emails']}")
    print(f"🚨 AOG Emergencies: {summary_stats['aog_count']}")
    print(f"✈️  Aircraft Found: {summary_stats['aircraft_count']}")
    print(f"📊 Categories: {', '.join(f'{k}({v})' for k, v in summary_stats['categories'].items())}")
    print(f"⚡ Priorities: {', '.join(f'{k}({v})' for k, v in summary_stats['priorities'].items())}")
    
    print(f"\n📁 OUTPUT FILES GENERATED:")
    print(f"=" * 50)
    data_dir = "aviation_data"
    for filename in ["processed_emails.csv", "support_tickets.csv", "processing_summary.csv"]:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"✅ {filepath} ({size:,} bytes)")
        else:
            print(f"❌ {filepath} (not found)")
    
    print(f"\n🎉 DEMO COMPLETE!")
    print(f"Open the CSV files in Excel to view detailed results!")
    print(f"All files are saved in the '{data_dir}' directory.")

if __name__ == "__main__":
    main()