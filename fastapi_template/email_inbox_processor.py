#!/usr/bin/env python3
"""
Embassy Aviation Mailbot - Real Email Inbox Processor
Connects to Gmail, Outlook, or IMAP to process actual aviation emails
"""

import imaplib
import email
import csv
import os
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from email.header import decode_header
import ssl

class AviationEmailClassifier:
    """Enhanced aviation email classifier for real emails."""
    
    def __init__(self):
        # Aviation-specific keywords (expanded for real-world use)
        self.aog_keywords = [
            'aog', 'urgent', 'emergency', 'grounded', 'critical', 'immediate',
            'stranded', 'stuck', 'failure', 'malfunction', 'broke', 'broken',
            'dispatch', 'cannot depart', 'unable to fly', 'flight delay'
        ]
        
        self.maintenance_keywords = [
            'maintenance', 'service', 'repair', 'inspection', 'check',
            'scheduled', 'routine', 'overhaul', 'component', 'system'
        ]
        
        self.parts_keywords = [
            'parts', 'component', 'delivery', 'shipment', 'inventory',
            'spare', 'replacement', 'supply', 'procurement'
        ]
        
        self.invoice_keywords = [
            'invoice', 'billing', 'payment', 'cost', 'charge', 'fee',
            'quote', 'estimate', 'financial', 'accounting'
        ]
        
        # Enhanced aircraft registration patterns
        self.aircraft_patterns = [
            r'\b[NC]-?[A-Z0-9]{2,6}\b',  # US/Canadian registrations
            r'\bG-[A-Z]{4}\b',           # UK registrations  
            r'\bD-[A-Z]{4}\b',           # German registrations
            r'\bF-[A-Z]{4}\b',           # French registrations
            r'\bJA[0-9]{4}[A-Z]?\b',     # Japanese registrations
        ]
        
    def classify_email(self, subject: str, body: str, sender: str) -> Dict:
        """Classify real aviation email with enhanced logic."""
        
        # Clean and normalize text
        text = self._clean_text(subject + ' ' + body).lower()
        
        # Extract aircraft registrations
        aircraft_list = self._extract_aircraft_registrations(subject + ' ' + body)
        primary_aircraft = aircraft_list[0] if aircraft_list else None
        
        # Enhanced AOG detection
        is_aog = self._detect_aog(text, subject)
        
        # Multi-criteria classification
        category, priority, confidence = self._classify_content(text, is_aog)
        
        # Sender-based adjustments
        category, priority = self._adjust_by_sender(sender, category, priority)
        
        return {
            'category': category,
            'priority': priority,
            'is_aog': is_aog,
            'aircraft_registration': primary_aircraft,
            'all_aircraft': aircraft_list,
            'confidence': confidence,
            'sender_domain': sender.split('@')[-1] if '@' in sender else sender
        }
    
    def _clean_text(self, text: str) -> str:
        """Clean email text for processing."""
        # Remove HTML tags, extra whitespace, special characters
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s-]', ' ', text)
        return text.strip()
    
    def _extract_aircraft_registrations(self, text: str) -> List[str]:
        """Extract all aircraft registrations from text."""
        aircraft = []
        for pattern in self.aircraft_patterns:
            matches = re.findall(pattern, text.upper())
            aircraft.extend(matches)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(aircraft))
    
    def _detect_aog(self, text: str, subject: str) -> bool:
        """Enhanced AOG detection logic."""
        
        # Critical keywords in subject (higher weight)
        subject_lower = subject.lower()
        critical_in_subject = any(keyword in subject_lower for keyword in self.aog_keywords[:6])
        
        # AOG keywords in body
        aog_in_body = any(keyword in text for keyword in self.aog_keywords)
        
        # Flight-related urgency patterns
        flight_urgency = any(pattern in text for pattern in [
            'flight.*delay', 'cannot.*depart', 'passengers.*waiting',
            'schedule.*impact', 'revenue.*loss'
        ])
        
        return critical_in_subject or (aog_in_body and flight_urgency)
    
    def _classify_content(self, text: str, is_aog: bool) -> Tuple[str, str, float]:
        """Multi-criteria content classification."""
        
        if is_aog:
            return 'AOG', 'CRITICAL', 0.95
        
        # Score each category
        maintenance_score = sum(1 for kw in self.maintenance_keywords if kw in text)
        parts_score = sum(1 for kw in self.parts_keywords if kw in text)  
        invoice_score = sum(1 for kw in self.invoice_keywords if kw in text)
        
        # Determine category based on highest score
        scores = {
            'MAINTENANCE': maintenance_score,
            'PARTS': parts_score,
            'INVOICE': invoice_score
        }
        
        top_category = max(scores, key=scores.get)
        top_score = scores[top_category]
        
        if top_score == 0:
            return 'GENERAL', 'NORMAL', 0.60
        
        # Determine priority and confidence
        if top_score >= 3:
            priority = 'HIGH'
            confidence = 0.90
        elif top_score >= 2:
            priority = 'NORMAL'
            confidence = 0.80
        else:
            priority = 'LOW'
            confidence = 0.70
            
        return top_category, priority, confidence
    
    def _adjust_by_sender(self, sender: str, category: str, priority: str) -> Tuple[str, str]:
        """Adjust classification based on sender patterns."""
        
        sender_lower = sender.lower()
        
        # Emergency/operations senders get priority boost
        if any(dept in sender_lower for dept in ['emergency', 'ops', 'dispatch', 'control']):
            if priority == 'NORMAL':
                priority = 'HIGH'
            elif priority == 'LOW':
                priority = 'NORMAL'
        
        # Billing/admin senders typically not urgent
        if any(dept in sender_lower for dept in ['billing', 'admin', 'accounting', 'finance']):
            if category == 'GENERAL':
                category = 'INVOICE'
        
        return category, priority

class EmailInboxProcessor:
    """Process real emails from IMAP/Gmail/Outlook inboxes."""
    
    def __init__(self, data_dir: str = "real_email_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.classifier = AviationEmailClassifier()
        
    def connect_to_inbox(self, email_provider: str, username: str, password: str, 
                        server: str = None, port: int = None) -> imaplib.IMAP4_SSL:
        """Connect to email inbox with provider-specific settings."""
        
        # Provider-specific configurations
        providers = {
            'gmail': {'server': 'imap.gmail.com', 'port': 993},
            'outlook': {'server': 'outlook.office365.com', 'port': 993},
            'yahoo': {'server': 'imap.mail.yahoo.com', 'port': 993},
            'icloud': {'server': 'imap.mail.me.com', 'port': 993}
        }
        
        if email_provider.lower() in providers:
            config = providers[email_provider.lower()]
            server = server or config['server']
            port = port or config['port']
        
        if not server:
            raise ValueError(f"Server required for provider: {email_provider}")
        
        print(f"🔐 Connecting to {server}:{port}...")
        
        # Create SSL connection
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(server, port, ssl_context=context)
        
        # Login
        try:
            result = mail.login(username, password)
            print(f"✅ Successfully connected to {email_provider} inbox")
            return mail
        except imaplib.IMAP4.error as e:
            print(f"❌ Login failed: {str(e)}")
            print("💡 For Gmail: Use App Password, not regular password")
            print("💡 For Outlook: Enable IMAP in settings")
            raise
    
    def fetch_emails(self, mail: imaplib.IMAP4_SSL, 
                    folder: str = 'INBOX',
                    days_back: int = 7,
                    sender_filter: str = None,
                    subject_filter: str = None,
                    max_emails: int = 50) -> List[Dict]:
        """Fetch emails with filtering options."""
        
        print(f"📧 Fetching emails from {folder} (last {days_back} days)...")
        
        # Select folder
        mail.select(folder)
        
        # Build search criteria
        search_criteria = []
        
        # Date filter
        since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        search_criteria.append(f'SINCE {since_date}')
        
        # Sender filter
        if sender_filter:
            search_criteria.append(f'FROM "{sender_filter}"')
        
        # Subject filter
        if subject_filter:
            search_criteria.append(f'SUBJECT "{subject_filter}"')
        
        # Search emails
        search_query = ' '.join(search_criteria)
        print(f"🔍 Search query: {search_query}")
        
        status, messages = mail.search(None, search_query)
        
        if status != 'OK':
            print(f"❌ Search failed: {status}")
            return []
        
        email_ids = messages[0].split()
        total_found = len(email_ids)
        
        if total_found == 0:
            print("📭 No emails found matching criteria")
            return []
        
        print(f"📬 Found {total_found} emails, processing up to {max_emails}...")
        
        # Limit number of emails to process
        email_ids = email_ids[-max_emails:] if len(email_ids) > max_emails else email_ids
        
        emails = []
        processed = 0
        
        for email_id in email_ids:
            try:
                # Fetch email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                
                # Parse email
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Extract email data
                email_data = self._extract_email_data(email_message)
                if email_data:
                    emails.append(email_data)
                    processed += 1
                    
                    if processed % 5 == 0:
                        print(f"📧 Processed {processed}/{len(email_ids)} emails...")
                        
            except Exception as e:
                print(f"⚠️  Error processing email {email_id}: {str(e)}")
                continue
        
        print(f"✅ Successfully processed {len(emails)} emails")
        return emails
    
    def _extract_email_data(self, email_message) -> Optional[Dict]:
        """Extract data from email message."""
        
        try:
            # Get subject
            subject = self._decode_header(email_message.get('Subject', ''))
            
            # Get sender
            sender = self._decode_header(email_message.get('From', ''))
            
            # Get date
            date_str = email_message.get('Date', '')
            
            # Get body
            body = self._extract_body(email_message)
            
            # Skip if essential data missing
            if not subject and not body:
                return None
            
            return {
                'subject': subject,
                'sender': sender,
                'date': date_str,
                'body': body,
                'message_id': email_message.get('Message-ID', ''),
            }
            
        except Exception as e:
            print(f"⚠️  Error extracting email data: {str(e)}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ''
        
        try:
            decoded_parts = decode_header(header)
            decoded_header = ''
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_header += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    decoded_header += part
                    
            return decoded_header.strip()
        except:
            return str(header)
    
    def _extract_body(self, email_message) -> str:
        """Extract email body text."""
        body = ''
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        charset = part.get_content_charset() or 'utf-8'
                        body_bytes = part.get_payload(decode=True)
                        if body_bytes:
                            body += body_bytes.decode(charset, errors='ignore')
            else:
                content_type = email_message.get_content_type()
                if content_type == 'text/plain':
                    charset = email_message.get_content_charset() or 'utf-8'
                    body_bytes = email_message.get_payload(decode=True)
                    if body_bytes:
                        body = body_bytes.decode(charset, errors='ignore')
            
            return body.strip()
        except:
            return ''
    
    def process_inbox_emails(self, config: Dict) -> Dict:
        """Main function to process emails from inbox."""
        
        print("🚁 EMBASSY AVIATION MAILBOT - REAL EMAIL PROCESSING")
        print("=" * 60)
        
        try:
            # Connect to inbox
            mail = self.connect_to_inbox(
                config['provider'],
                config['username'], 
                config['password'],
                config.get('server'),
                config.get('port')
            )
            
            # Fetch emails
            emails = self.fetch_emails(
                mail,
                config.get('folder', 'INBOX'),
                config.get('days_back', 7),
                config.get('sender_filter'),
                config.get('subject_filter'),
                config.get('max_emails', 50)
            )
            
            # Close connection
            mail.close()
            mail.logout()
            
            if not emails:
                print("📭 No emails to process")
                return {'total_emails': 0}
            
            # Process and classify emails
            return self._process_and_save_emails(emails)
            
        except Exception as e:
            print(f"❌ Error processing inbox: {str(e)}")
            return {'error': str(e)}
    
    def _process_and_save_emails(self, emails: List[Dict]) -> Dict:
        """Process and classify real emails."""
        
        print(f"\n🤖 CLASSIFYING {len(emails)} REAL AVIATION EMAILS")
        print("=" * 50)
        
        processed_results = []
        
        for i, email_data in enumerate(emails, 1):
            print(f"\n📧 Email {i}/{len(emails)}")
            print(f"From: {email_data['sender']}")
            print(f"Subject: {email_data['subject'][:80]}...")
            
            # Classify email
            result = self.classifier.classify_email(
                email_data['subject'],
                email_data['body'],
                email_data['sender']
            )
            
            # Create processed record
            processed_email = {
                'email_id': f"REAL-{datetime.now().strftime('%Y%m%d')}-{i:03d}",
                'ticket_number': f"TICKET-REAL-{i:03d}",
                'timestamp': datetime.now().isoformat(),
                'original_date': email_data['date'],
                'sender': email_data['sender'],
                'sender_domain': result['sender_domain'],
                'subject': email_data['subject'],
                'body_preview': email_data['body'][:200] + '...' if len(email_data['body']) > 200 else email_data['body'],
                'category': result['category'],
                'priority': result['priority'],
                'is_aog': result['is_aog'],
                'aircraft_registration': result['aircraft_registration'] or 'N/A',
                'all_aircraft': ', '.join(result['all_aircraft']) if result['all_aircraft'] else 'N/A',
                'confidence': result['confidence'],
                'message_id': email_data['message_id'],
                'status': 'CLASSIFIED'
            }
            
            processed_results.append(processed_email)
            
            # Print results
            print(f"→ Category: {result['category']}")
            print(f"→ Priority: {result['priority']}")
            print(f"→ AOG Emergency: {'🚨 YES' if result['is_aog'] else '✅ NO'}")
            print(f"→ Aircraft: {result['aircraft_registration'] or 'Not detected'}")
            if result['all_aircraft'] and len(result['all_aircraft']) > 1:
                print(f"→ All Aircraft: {', '.join(result['all_aircraft'])}")
            print(f"→ Confidence: {result['confidence']:.2f}")
        
        # Save results
        summary_stats = self._save_real_email_results(processed_results)
        
        return summary_stats
    
    def _save_real_email_results(self, emails: List[Dict]) -> Dict:
        """Save real email processing results to CSV."""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # File paths
        emails_file = os.path.join(self.data_dir, f"real_emails_{timestamp}.csv")
        tickets_file = os.path.join(self.data_dir, f"real_tickets_{timestamp}.csv")
        summary_file = os.path.join(self.data_dir, f"real_summary_{timestamp}.csv")
        
        # Save detailed email data
        with open(emails_file, 'w', newline='', encoding='utf-8') as f:
            if emails:
                writer = csv.DictWriter(f, fieldnames=emails[0].keys())
                writer.writeheader()
                writer.writerows(emails)
        
        # Save tickets summary
        with open(tickets_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Ticket Number', 'Category', 'Priority', 'AOG Emergency',
                'Aircraft Registration', 'Sender Domain', 'Subject',
                'Original Date', 'Processed Date', 'Status'
            ])
            
            for email in emails:
                writer.writerow([
                    email['ticket_number'],
                    email['category'],
                    email['priority'],
                    'YES' if email['is_aog'] else 'NO',
                    email['aircraft_registration'],
                    email['sender_domain'],
                    email['subject'],
                    email['original_date'],
                    email['timestamp'][:10],
                    email['status']
                ])
        
        # Generate summary statistics
        summary_stats = self._generate_real_email_stats(emails)
        
        # Save summary
        with open(summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Real Emails Processed', summary_stats['total_emails']])
            writer.writerow(['AOG Emergencies Detected', summary_stats['aog_count']])
            writer.writerow(['Unique Aircraft Found', summary_stats['aircraft_count']])
            writer.writerow(['Unique Sender Domains', summary_stats['domain_count']])
            writer.writerow(['Processing Date', summary_stats['report_date']])
            writer.writerow(['', ''])
            writer.writerow(['Category Distribution', 'Count'])
            
            for category, count in summary_stats['categories'].items():
                writer.writerow([category, count])
            
            writer.writerow(['', ''])
            writer.writerow(['Priority Distribution', 'Count'])
            for priority, count in summary_stats['priorities'].items():
                writer.writerow([priority, count])
            
            writer.writerow(['', ''])
            writer.writerow(['Top Sender Domains', 'Email Count'])
            for domain, count in summary_stats['top_domains'].items():
                writer.writerow([domain, count])
        
        print(f"\n📊 REAL EMAIL PROCESSING COMPLETE!")
        print(f"=" * 50)
        print(f"✅ Processed {len(emails)} real emails")
        print(f"✅ Files saved to '{self.data_dir}/' directory")
        print(f"📧 {os.path.basename(emails_file)} - Complete email data")
        print(f"🎫 {os.path.basename(tickets_file)} - Ticket summaries")
        print(f"📈 {os.path.basename(summary_file)} - Processing statistics")
        
        return summary_stats
    
    def _generate_real_email_stats(self, emails: List[Dict]) -> Dict:
        """Generate statistics for real email processing."""
        
        categories = {}
        priorities = {}
        domains = {}
        aog_count = 0
        aircraft_found = set()
        
        for email in emails:
            # Count categories
            cat = email['category']
            categories[cat] = categories.get(cat, 0) + 1
            
            # Count priorities  
            pri = email['priority']
            priorities[pri] = priorities.get(pri, 0) + 1
            
            # Count domains
            domain = email['sender_domain']
            domains[domain] = domains.get(domain, 0) + 1
            
            # Count AOG
            if email['is_aog']:
                aog_count += 1
            
            # Collect aircraft
            if email['aircraft_registration'] != 'N/A':
                aircraft_found.add(email['aircraft_registration'])
            
            # Add aircraft from all_aircraft field
            if email['all_aircraft'] != 'N/A':
                for aircraft in email['all_aircraft'].split(', '):
                    if aircraft.strip():
                        aircraft_found.add(aircraft.strip())
        
        # Get top domains
        top_domains = dict(sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return {
            'total_emails': len(emails),
            'aog_count': aog_count,
            'aircraft_count': len(aircraft_found),
            'domain_count': len(domains),
            'categories': categories,
            'priorities': priorities,
            'top_domains': top_domains,
            'report_date': datetime.now().isoformat()
        }

def main():
    """Main function for real email processing."""
    
    print("🚁 EMBASSY AVIATION MAILBOT - REAL EMAIL INBOX PROCESSOR")
    print("=" * 70)
    print()
    print("This tool connects to your real email inbox and processes aviation emails.")
    print("Supported providers: Gmail, Outlook, Yahoo, iCloud, Custom IMAP")
    print()
    
    # Email configuration
    config = {
        'provider': input("📧 Email provider (gmail/outlook/yahoo/icloud/custom): ").strip().lower(),
        'username': input("👤 Email address: ").strip(),
        'password': input("🔐 Password (App Password for Gmail): ").strip(),
        'days_back': int(input("📅 Days back to search (default 7): ").strip() or "7"),
        'max_emails': int(input("📊 Max emails to process (default 50): ").strip() or "50"),
    }
    
    # Optional filters
    sender_filter = input("🔍 Filter by sender (optional): ").strip()
    if sender_filter:
        config['sender_filter'] = sender_filter
    
    subject_filter = input("📝 Filter by subject keywords (optional): ").strip()
    if subject_filter:
        config['subject_filter'] = subject_filter
    
    # Custom server settings for non-standard providers
    if config['provider'] == 'custom':
        config['server'] = input("🌐 IMAP server: ").strip()
        config['port'] = int(input("🔌 IMAP port (default 993): ").strip() or "993")
    
    print("\n🚀 Starting real email processing...")
    
    # Process emails
    processor = EmailInboxProcessor()
    result = processor.process_inbox_emails(config)
    
    if 'error' in result:
        print(f"\n❌ Processing failed: {result['error']}")
        return
    
    # Display results
    print(f"\n📈 REAL EMAIL PROCESSING RESULTS")
    print(f"=" * 50)
    print(f"🎯 Total Emails: {result['total_emails']}")
    print(f"🚨 AOG Emergencies: {result['aog_count']}")
    print(f"✈️  Unique Aircraft: {result['aircraft_count']}")
    print(f"🌐 Sender Domains: {result['domain_count']}")
    print(f"📊 Categories: {', '.join(f'{k}({v})' for k, v in result['categories'].items())}")
    print(f"⚡ Priorities: {', '.join(f'{k}({v})' for k, v in result['priorities'].items())}")
    
    print(f"\n🎉 REAL EMAIL PROCESSING COMPLETE!")
    print(f"Check the 'real_email_data' directory for detailed CSV reports.")

if __name__ == "__main__":
    main()