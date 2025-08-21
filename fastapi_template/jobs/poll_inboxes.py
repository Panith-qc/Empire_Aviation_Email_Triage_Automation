"""Main polling job for processing email inboxes."""

import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.pipeline import EmailProcessingPipeline
from app.utils.logging import setup_logging, get_logger, CorrelationContextManager

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def main():
    """Main polling job entry point."""
    try:
        with CorrelationContextManager() as correlation_id:
            logger.info("Starting email polling job", correlation_id=correlation_id)
            
            # Initialize pipeline
            pipeline = EmailProcessingPipeline()
            
            # Process all mailboxes
            results = await pipeline.process_all_mailboxes()
            
            logger.info(
                "Email polling job completed",
                correlation_id=correlation_id,
                total_processed=results["total_processed"],
                total_errors=results["total_errors"]
            )
            
            # Return non-zero exit code if there were errors
            if results["total_errors"] > 0:
                logger.warning("Job completed with errors", error_count=results["total_errors"])
                return 1
            
            return 0
            
    except Exception as e:
        logger.error("Email polling job failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)