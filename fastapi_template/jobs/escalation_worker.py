"""Escalation processing worker job."""

import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.escalation.engine import EscalationEngine
from app.utils.logging import setup_logging, get_logger, CorrelationContextManager

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def main():
    """Main escalation worker entry point."""
    try:
        with CorrelationContextManager() as correlation_id:
            logger.info("Starting escalation worker job", correlation_id=correlation_id)
            
            # Initialize escalation engine
            escalation_engine = EscalationEngine()
            
            # Process pending escalations
            processed_count = await escalation_engine.process_pending_escalations()
            
            logger.info(
                "Escalation worker job completed",
                correlation_id=correlation_id,
                processed_count=processed_count
            )
            
            return 0
            
    except Exception as e:
        logger.error("Escalation worker job failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)