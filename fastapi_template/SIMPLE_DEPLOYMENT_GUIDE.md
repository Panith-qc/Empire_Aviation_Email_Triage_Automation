# 🚁 Embassy Aviation Mailbot - Simple Deployment Guide

## 📋 Quick Start (No Database Setup Required!)

### 1. Install Python Requirements
```bash
pip install -r simple_requirements.txt
```

### 2. Run the Application
```bash
python run_simple.py
```

### 3. Open Your Browser
- **Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 🎯 What This System Does

### ✅ Immediate Features (No Setup Required)
- **Email Classification**: Uses AI to categorize aviation emails
- **AOG Detection**: Identifies Aircraft on Ground emergencies
- **Aircraft Registration**: Extracts aircraft tail numbers (N123AB, etc.)
- **Priority Assignment**: CRITICAL, HIGH, NORMAL based on content
- **CSV Storage**: All data stored in simple CSV files
- **HTML Dashboard**: Visual interface to monitor processing
- **Excel Reports**: Download processing statistics as CSV/Excel

### 📊 Available Reports
- Total emails processed
- Categories breakdown (AOG, SERVICE, INVOICE, etc.)
- Priority distribution
- Aircraft registrations found
- Processing timestamps

## 🧪 Testing the System

### Method 1: Process Sample Emails (Automatic)
1. Go to http://localhost:8000
2. Click "Process Sample Emails" 
3. View results on dashboard

### Method 2: Process Custom Email (API)
```bash
curl -X POST "http://localhost:8000/process-email" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "URGENT AOG - Aircraft N789XY grounded at JFK",
    "body": "Engine failure requires immediate assistance",
    "sender": "ops@airline.com"
  }'
```

### Method 3: Use Web Interface
1. Go to http://localhost:8000/docs
2. Try the `/process-email` endpoint
3. Use sample data provided

## 📁 Data Storage

All data is stored in CSV files in the `data/` directory:
- `data/emails.csv` - All processed emails
- `data/tickets.csv` - Generated tickets with classifications
- `data/activities.csv` - System activity log

## 📈 Viewing Results

### Dashboard (Recommended)
- Visit http://localhost:8000 for visual dashboard
- Real-time statistics and charts
- Download reports directly

### CSV Reports
- Click "Download CSV Report" on dashboard
- Opens in Excel for analysis
- Contains all processing data

### API Data
- GET `/reports/summary` - Summary statistics
- GET `/reports/dashboard-data` - All data in JSON format

## 🚀 Sample Test Data

The system includes 5 sample aviation emails:
1. **AOG Emergency**: "URGENT AOG - Aircraft N789XY grounded at JFK"
2. **Hydraulic Emergency**: "EMERGENCY - N999EF hydraulic system failure"
3. **Scheduled Maintenance**: "Scheduled maintenance request N123AB"
4. **Parts Delivery**: "Parts delivery confirmation N456CD" 
5. **Invoice Inquiry**: "Invoice inquiry #INV-12345"

## 🔧 System Requirements

- Python 3.8+ 
- 50MB disk space
- No database setup required
- Works on Windows, Mac, Linux

## ✅ Success Indicators

After running, you should see:
- Server starts on http://localhost:8000
- Dashboard loads with "Embassy Aviation Mailbot" title
- Sample emails process successfully
- CSV files created in `data/` directory
- Reports downloadable as CSV/Excel

## 🎯 Expected Output

### Dashboard Statistics
- Total Emails: 5 (after processing samples)
- Categories: AOG (2), SERVICE (1), INVOICE (1), MAINTENANCE (1)
- AOG Emergencies: 2 detected
- Aircraft Found: N789XY, N999EF, N123AB, N456CD

### CSV Report Contents
- Ticket numbers (EMB-20231218-001, etc.)
- Classifications and priorities
- Aircraft registrations extracted
- Processing timestamps
- Customer email addresses

## 🚨 Troubleshooting

### "Module not found" errors
```bash
pip install -r simple_requirements.txt
```

### "Port already in use"
```bash
# Kill existing process or change port in run_simple.py
python run_simple.py --port 8001
```

### "Permission denied" for data directory
```bash
mkdir data
chmod 755 data
```

## 📞 Support

This simplified version works immediately without any database setup. All data is stored in CSV files that can be opened in Excel for analysis.

**Status**: ✅ Ready for immediate testing and demonstration!