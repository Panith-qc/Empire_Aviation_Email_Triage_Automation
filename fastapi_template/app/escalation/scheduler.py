"""Escalation scheduler for managing timed escalations."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.escalation.engine import EscalationEngine
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EscalationScheduler:
    """Scheduler for managing escalation timing and processing."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.escalation_engine = EscalationEngine()
        self.is_running = False
    
    async def start(self) -> None:
        """Start the escalation scheduler."""
        if self.is_running:
            logger.warning("Escalation scheduler already running")
            return
        
        try:
            # Add escalation processing job
            self.scheduler.add_job(
                self._process_escalations,
                trigger=IntervalTrigger(
                    seconds=settings.POLLING_INTERVAL_SECONDS // 2  # Process escalations more frequently
                ),
                id="process_escalations",
                name="Process Pending Escalations",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30
            )
            
            # Add cleanup job (daily at 2 AM)
            self.scheduler.add_job(
                self._cleanup_old_escalations,
                trigger=CronTrigger(hour=2, minute=0),
                id="cleanup_escalations",
                name="Cleanup Old Escalations",
                max_instances=1
            )
            
            # Add health check job
            self.scheduler.add_job(
                self._health_check,
                trigger=IntervalTrigger(minutes=5),
                id="escalation_health_check",
                name="Escalation Health Check",
                max_instances=1
            )
            
            self.scheduler.start()
            self.is_running = True
            
            logger.info("Escalation scheduler started")
            
        except Exception as e:
            logger.error("Error starting escalation scheduler", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the escalation scheduler."""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Escalation scheduler stopped")
            
        except Exception as e:
            logger.error("Error stopping escalation scheduler", error=str(e))
    
    async def _process_escalations(self) -> None:
        """Process pending escalations."""
        try:
            processed_count = await self.escalation_engine.process_pending_escalations()
            
            if processed_count > 0:
                logger.info("Processed escalations", count=processed_count)
                
        except Exception as e:
            logger.error("Error processing escalations", error=str(e))
    
    async def _cleanup_old_escalations(self) -> None:
        """Clean up old escalation data."""
        try:
            # Implementation for cleaning up old resolved tickets and escalation steps
            # This would typically remove escalation steps for tickets older than retention period
            logger.info("Escalation cleanup job executed")
            
        except Exception as e:
            logger.error("Error in escalation cleanup", error=str(e))
    
    async def _health_check(self) -> None:
        """Perform health check on escalation system."""
        try:
            # Check if escalation engine is responsive
            # This could include checking database connectivity, external services, etc.
            logger.debug("Escalation health check completed")
            
        except Exception as e:
            logger.error("Escalation health check failed", error=str(e))
    
    def get_job_status(self) -> dict:
        """Get status of scheduled jobs."""
        if not self.is_running:
            return {"status": "stopped", "jobs": []}
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return {
            "status": "running",
            "jobs": jobs
        }
    
    async def trigger_escalation_processing(self) -> int:
        """Manually trigger escalation processing."""
        try:
            processed_count = await self.escalation_engine.process_pending_escalations()
            logger.info("Manual escalation processing triggered", count=processed_count)
            return processed_count
            
        except Exception as e:
            logger.error("Error in manual escalation processing", error=str(e))
            return 0