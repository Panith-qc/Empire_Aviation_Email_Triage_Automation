"""Monthly report generation job."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.reporting import ReportingService
from app.utils.logging import setup_logging, get_logger, CorrelationContextManager

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def main():
    """Main report generation entry point."""
    try:
        with CorrelationContextManager() as correlation_id:
            logger.info("Starting monthly report generation job", correlation_id=correlation_id)
            
            # Initialize reporting service
            reporting_service = ReportingService()
            
            # Generate report for last month
            now = datetime.utcnow()
            if now.month == 1:
                year = now.year - 1
                month = 12
            else:
                year = now.year
                month = now.month - 1
            
            # Generate both JSON and CSV formats
            json_report = await reporting_service.generate_monthly_report(year, month, "json")
            csv_report = await reporting_service.generate_monthly_report(year, month, "csv")
            
            # Save reports to files (in production, might send via email or upload to storage)
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            
            # Save JSON report
            json_file = reports_dir / f"embassy_aviation_report_{year}_{month:02d}.json"
            with open(json_file, 'w') as f:
                import json
                json.dump(json_report, f, indent=2)
            
            # Save CSV report
            csv_file = reports_dir / f"embassy_aviation_report_{year}_{month:02d}.csv"
            with open(csv_file, 'w') as f:
                f.write(csv_report)
            
            logger.info(
                "Monthly report generation completed",
                correlation_id=correlation_id,
                year=year,
                month=month,
                json_file=str(json_file),
                csv_file=str(csv_file)
            )
            
            return 0
            
    except Exception as e:
        logger.error("Monthly report generation failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)