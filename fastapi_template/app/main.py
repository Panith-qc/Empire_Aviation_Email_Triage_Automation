"""Main FastAPI application for Embassy Aviation Mailbot."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.config import settings
from app.models.database import create_tables
from app.services.pipeline import EmailProcessingPipeline
from app.services.reporting import ReportingService
from app.services.monitoring import MonitoringService
from app.escalation.scheduler import EscalationScheduler
from app.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Global service instances
pipeline_service: EmailProcessingPipeline = None
reporting_service: ReportingService = None
monitoring_service: MonitoringService = None
escalation_scheduler: EscalationScheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global pipeline_service, reporting_service, monitoring_service, escalation_scheduler
    
    logger.info("Starting Embassy Aviation Mailbot")
    
    try:
        # Create database tables
        await create_tables()
        logger.info("Database tables created/verified")
        
        # Initialize services
        pipeline_service = EmailProcessingPipeline()
        reporting_service = ReportingService()
        monitoring_service = MonitoringService()
        escalation_scheduler = EscalationScheduler()
        
        # Start escalation scheduler
        await escalation_scheduler.start()
        logger.info("Escalation scheduler started")
        
        # Perform initial health check
        health_status = await monitoring_service.get_system_health()
        logger.info("Initial health check completed", status=health_status["overall_status"])
        
        logger.info("Embassy Aviation Mailbot started successfully")
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Embassy Aviation Mailbot")
    
    try:
        if escalation_scheduler:
            await escalation_scheduler.stop()
            logger.info("Escalation scheduler stopped")
        
        logger.info("Embassy Aviation Mailbot shutdown completed")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-driven email triage automation system for Embassy Aviation",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://embassy-aviation.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else ["embassy-aviation.com", "*.embassy-aviation.com"]
)


# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status."""
    if not monitoring_service:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        health_status = await monitoring_service.get_system_health()
        
        # Return appropriate HTTP status based on health
        if health_status["overall_status"] == "critical":
            return JSONResponse(
                status_code=503,
                content=health_status
            )
        elif health_status["overall_status"] == "degraded":
            return JSONResponse(
                status_code=200,
                content=health_status
            )
        else:
            return health_status
            
    except Exception as e:
        logger.error("Error in detailed health check", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "overall_status": "critical",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# Processing endpoints
@app.post("/api/v1/process/mailboxes")
async def process_all_mailboxes(background_tasks: BackgroundTasks):
    """Manually trigger processing of all mailboxes."""
    if not pipeline_service:
        raise HTTPException(status_code=503, detail="Pipeline service not initialized")
    
    try:
        # Run processing in background
        background_tasks.add_task(pipeline_service.process_all_mailboxes)
        
        return {
            "message": "Email processing started",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Error starting email processing", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/process/mailbox/{mailbox}")
async def process_single_mailbox(mailbox: str, background_tasks: BackgroundTasks):
    """Manually trigger processing of a specific mailbox."""
    if not pipeline_service:
        raise HTTPException(status_code=503, detail="Pipeline service not initialized")
    
    try:
        # Validate mailbox
        if mailbox not in settings.GRAPH_USER_MAILBOXES:
            raise HTTPException(
                status_code=400, 
                detail=f"Mailbox {mailbox} not configured"
            )
        
        # Run processing in background
        background_tasks.add_task(pipeline_service.process_mailbox, mailbox)
        
        return {
            "message": f"Processing started for mailbox: {mailbox}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error starting mailbox processing", mailbox=mailbox, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Escalation endpoints
@app.post("/api/v1/escalation/process")
async def trigger_escalation_processing(background_tasks: BackgroundTasks):
    """Manually trigger escalation processing."""
    if not escalation_scheduler:
        raise HTTPException(status_code=503, detail="Escalation scheduler not initialized")
    
    try:
        processed_count = await escalation_scheduler.trigger_escalation_processing()
        
        return {
            "message": "Escalation processing completed",
            "processed_count": processed_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Error in escalation processing", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/escalation/status")
async def get_escalation_status():
    """Get escalation scheduler status."""
    if not escalation_scheduler:
        raise HTTPException(status_code=503, detail="Escalation scheduler not initialized")
    
    try:
        status = escalation_scheduler.get_job_status()
        return status
        
    except Exception as e:
        logger.error("Error getting escalation status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Reporting endpoints
@app.get("/api/v1/reports/monthly/{year}/{month}")
async def get_monthly_report(year: int, month: int, format: str = "json"):
    """Get monthly report."""
    if not reporting_service:
        raise HTTPException(status_code=503, detail="Reporting service not initialized")
    
    try:
        # Validate parameters
        if year < 2020 or year > datetime.utcnow().year + 1:
            raise HTTPException(status_code=400, detail="Invalid year")
        
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="Invalid month")
        
        if format not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
        
        report = await reporting_service.generate_monthly_report(year, month, format)
        
        if format == "csv":
            return JSONResponse(
                content={"csv_data": report},
                headers={"Content-Type": "application/json"}
            )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating monthly report", year=year, month=month, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/reports/dashboard")
async def get_dashboard_metrics():
    """Get real-time dashboard metrics."""
    if not reporting_service:
        raise HTTPException(status_code=503, detail="Reporting service not initialized")
    
    try:
        metrics = await reporting_service.get_dashboard_metrics()
        return metrics
        
    except Exception as e:
        logger.error("Error getting dashboard metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Monitoring endpoints
@app.get("/api/v1/monitoring/metrics")
async def get_system_metrics():
    """Get system performance metrics."""
    if not monitoring_service:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        health_status = await monitoring_service.get_system_health()
        return health_status
        
    except Exception as e:
        logger.error("Error getting system metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/monitoring/performance")
async def get_performance_metrics(hours: int = 24):
    """Get performance metrics over time."""
    if not monitoring_service:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        # Validate hours parameter
        if hours < 1 or hours > 168:  # Max 1 week
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")
        
        metrics = await monitoring_service.get_performance_metrics(hours)
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting performance metrics", hours=hours, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Configuration endpoints
@app.get("/api/v1/config/info")
async def get_config_info():
    """Get basic configuration information."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "features": {
            "ml_classification": settings.ENABLE_ML_CLASSIFICATION,
            "escalation": settings.ENABLE_ESCALATION,
            "sms_alerts": settings.ENABLE_SMS_ALERTS
        },
        "configured_mailboxes": len(settings.GRAPH_USER_MAILBOXES),
        "polling_interval_seconds": settings.POLLING_INTERVAL_SECONDS,
        "max_emails_per_batch": settings.MAX_EMAILS_PER_BATCH
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with structured logging."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions with structured logging."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )


# Run application
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )