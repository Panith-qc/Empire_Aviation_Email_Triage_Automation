"""Simple launcher for Embassy Aviation Mailbot."""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, '.')

def main():
    print("🚁 Embassy Aviation Mailbot - Simple Version")
    print("=" * 50)
    print("Starting email triage automation system...")
    print()
    print("📊 Dashboard: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("🔧 Health Check: http://localhost:8000/health")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Create data directory
    os.makedirs("data", exist_ok=True)
    
    # Import and run
    import uvicorn
    from app.simple_main import app
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()