"""Simple CSV-based storage for email triage system."""

import csv
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import uuid


class CSVStorage:
    """Simple CSV-based storage system."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize CSV files
        self.emails_file = os.path.join(data_dir, "emails.csv")
        self.tickets_file = os.path.join(data_dir, "tickets.csv")
        self.activities_file = os.path.join(data_dir, "activities.csv")
        
        self._initialize_files()
    
    def _initialize_files(self):
        """Initialize CSV files with headers if they don't exist."""
        
        # Emails CSV
        if not os.path.exists(self.emails_file):
            with open(self.emails_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'message_id', 'subject', 'sender', 'body_text', 
                    'received_at', 'processed_at', 'status'
                ])
        
        # Tickets CSV
        if not os.path.exists(self.tickets_file):
            with open(self.tickets_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'ticket_number', 'title', 'category', 'priority', 
                    'status', 'customer_email', 'aircraft_registration', 
                    'is_aog', 'created_at', 'updated_at'
                ])
        
        # Activities CSV
        if not os.path.exists(self.activities_file):
            with open(self.activities_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'ticket_id', 'activity_type', 'title', 'description',
                    'actor_type', 'created_at'
                ])
    
    def save_email(self, email_data: Dict) -> str:
        """Save email to CSV."""
        email_id = str(uuid.uuid4())
        email_data['id'] = email_id
        email_data['received_at'] = datetime.now().isoformat()
        email_data['status'] = 'received'
        
        with open(self.emails_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                email_data['id'], email_data['message_id'], email_data['subject'],
                email_data['sender'], email_data['body_text'], email_data['received_at'],
                email_data.get('processed_at', ''), email_data['status']
            ])
        
        return email_id
    
    def save_ticket(self, ticket_data: Dict) -> str:
        """Save ticket to CSV."""
        ticket_id = str(uuid.uuid4())
        ticket_data['id'] = ticket_id
        ticket_data['created_at'] = datetime.now().isoformat()
        ticket_data['updated_at'] = datetime.now().isoformat()
        
        with open(self.tickets_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                ticket_data['id'], ticket_data['ticket_number'], ticket_data['title'],
                ticket_data['category'], ticket_data['priority'], ticket_data['status'],
                ticket_data['customer_email'], ticket_data.get('aircraft_registration', ''),
                ticket_data.get('is_aog', False), ticket_data['created_at'], ticket_data['updated_at']
            ])
        
        return ticket_id
    
    def save_activity(self, activity_data: Dict) -> str:
        """Save activity to CSV."""
        activity_id = str(uuid.uuid4())
        activity_data['id'] = activity_id
        activity_data['created_at'] = datetime.now().isoformat()
        
        with open(self.activities_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                activity_data['id'], activity_data.get('ticket_id', ''),
                activity_data['activity_type'], activity_data['title'],
                activity_data.get('description', ''), activity_data['actor_type'],
                activity_data['created_at']
            ])
        
        return activity_id
    
    def get_emails_df(self) -> pd.DataFrame:
        """Get emails as pandas DataFrame."""
        try:
            return pd.read_csv(self.emails_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return pd.DataFrame()
    
    def get_tickets_df(self) -> pd.DataFrame:
        """Get tickets as pandas DataFrame."""
        try:
            return pd.read_csv(self.tickets_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return pd.DataFrame()
    
    def get_activities_df(self) -> pd.DataFrame:
        """Get activities as pandas DataFrame."""
        try:
            return pd.read_csv(self.activities_file)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return pd.DataFrame()
    
    def generate_summary_report(self) -> Dict:
        """Generate summary statistics."""
        emails_df = self.get_emails_df()
        tickets_df = self.get_tickets_df()
        
        if emails_df.empty and tickets_df.empty:
            return {
                'total_emails': 0,
                'total_tickets': 0,
                'categories': {},
                'priorities': {},
                'aog_count': 0
            }
        
        # Email statistics
        total_emails = len(emails_df)
        
        # Ticket statistics
        total_tickets = len(tickets_df)
        categories = tickets_df['category'].value_counts().to_dict() if not tickets_df.empty else {}
        priorities = tickets_df['priority'].value_counts().to_dict() if not tickets_df.empty else {}
        aog_count = len(tickets_df[tickets_df['is_aog'] == True]) if not tickets_df.empty else 0
        
        return {
            'total_emails': total_emails,
            'total_tickets': total_tickets,
            'categories': categories,
            'priorities': priorities,
            'aog_count': aog_count,
            'processing_rate': f"{total_emails} emails processed",
            'report_generated_at': datetime.now().isoformat()
        }