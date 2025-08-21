"""Monitoring and health check service."""

import asyncio
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db_session, engine
from app.models.ticket import Ticket
from app.models.message_state import MessageState, ProcessingStatus
from app.connectors.email_graph import GraphEmailConnector
from app.connectors.email_smtp import SMTPEmailConnector
from app.connectors.twilio_sms import TwilioSMSConnector
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MonitoringService:
    """Service for system monitoring and health checks."""
    
    def __init__(self):
        self.graph_connector = GraphEmailConnector()
        self.smtp_connector = SMTPEmailConnector()
        self.sms_connector = TwilioSMSConnector()
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        try:
            health_status = {
                "overall_status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {},
                "metrics": {},
                "alerts": []
            }
            
            # Check database connectivity
            db_health = await self._check_database_health()
            health_status["components"]["database"] = db_health
            
            # Check external services
            graph_health = await self._check_graph_api_health()
            health_status["components"]["graph_api"] = graph_health
            
            smtp_health = await self._check_smtp_health()
            health_status["components"]["smtp"] = smtp_health
            
            sms_health = await self._check_sms_health()
            health_status["components"]["sms"] = sms_health
            
            # Get system metrics
            system_metrics = await self._get_system_metrics()
            health_status["metrics"] = system_metrics
            
            # Get processing metrics
            processing_metrics = await self._get_processing_metrics()
            health_status["metrics"]["processing"] = processing_metrics
            
            # Determine overall status
            component_statuses = [comp["status"] for comp in health_status["components"].values()]
            if "critical" in component_statuses:
                health_status["overall_status"] = "critical"
            elif "degraded" in component_statuses:
                health_status["overall_status"] = "degraded"
            
            # Generate alerts
            alerts = await self._generate_alerts(health_status)
            health_status["alerts"] = alerts
            
            return health_status
            
        except Exception as e:
            logger.error("Error getting system health", error=str(e))
            return {
                "overall_status": "critical",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = datetime.utcnow()
            
            async with get_db_session() as session:
                # Test basic connectivity
                await session.execute(text("SELECT 1"))
                
                # Test table access
                result = await session.execute(select(func.count(Ticket.id)))
                ticket_count = result.scalar()
                
                # Test recent activity
                recent_time = datetime.utcnow() - timedelta(hours=1)
                result = await session.execute(
                    select(func.count(Ticket.id))
                    .where(Ticket.created_at >= recent_time)
                )
                recent_tickets = result.scalar()
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "total_tickets": ticket_count,
                "recent_tickets_1h": recent_tickets,
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {
                "status": "critical",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _check_graph_api_health(self) -> Dict[str, Any]:
        """Check Microsoft Graph API connectivity."""
        try:
            start_time = datetime.utcnow()
            
            # Test connection
            is_healthy = await self.graph_connector.check_connection()
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if is_healthy:
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "configured_mailboxes": len(settings.GRAPH_USER_MAILBOXES),
                    "last_check": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "degraded",
                    "error": "Connection test failed",
                    "response_time_ms": round(response_time, 2),
                    "last_check": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Graph API health check failed", error=str(e))
            return {
                "status": "critical",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _check_smtp_health(self) -> Dict[str, Any]:
        """Check SMTP connectivity."""
        try:
            start_time = datetime.utcnow()
            
            # Test connection
            is_healthy = await self.smtp_connector.check_connection()
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if is_healthy:
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "smtp_host": settings.SMTP_HOST,
                    "smtp_port": settings.SMTP_PORT,
                    "last_check": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "degraded",
                    "error": "SMTP connection test failed",
                    "response_time_ms": round(response_time, 2),
                    "last_check": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("SMTP health check failed", error=str(e))
            return {
                "status": "critical",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _check_sms_health(self) -> Dict[str, Any]:
        """Check Twilio SMS connectivity."""
        try:
            start_time = datetime.utcnow()
            
            # Test connection
            is_healthy = await self.sms_connector.check_connection()
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if is_healthy:
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "sms_enabled": settings.ENABLE_SMS_ALERTS,
                    "last_check": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "degraded" if settings.ENABLE_SMS_ALERTS else "disabled",
                    "error": "Twilio connection test failed" if settings.ENABLE_SMS_ALERTS else "SMS disabled",
                    "response_time_ms": round(response_time, 2),
                    "last_check": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("SMS health check failed", error=str(e))
            return {
                "status": "critical" if settings.ENABLE_SMS_ALERTS else "disabled",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            return {
                "cpu": {
                    "usage_percent": round(cpu_percent, 2),
                    "core_count": psutil.cpu_count()
                },
                "memory": {
                    "usage_percent": round(memory.percent, 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "total_gb": round(memory.total / (1024**3), 2)
                },
                "disk": {
                    "usage_percent": round(disk.percent, 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "total_gb": round(disk.total / (1024**3), 2)
                }
            }
            
        except Exception as e:
            logger.error("Error getting system metrics", error=str(e))
            return {"error": str(e)}
    
    async def _get_processing_metrics(self) -> Dict[str, Any]:
        """Get email processing metrics."""
        try:
            async with get_db_session() as session:
                now = datetime.utcnow()
                last_hour = now - timedelta(hours=1)
                last_24h = now - timedelta(hours=24)
                
                # Messages processed in last hour
                result = await session.execute(
                    select(func.count(MessageState.id))
                    .where(and_(
                        MessageState.status == ProcessingStatus.COMPLETED,
                        MessageState.processing_completed_at >= last_hour
                    ))
                )
                processed_last_hour = result.scalar() or 0
                
                # Messages processed in last 24h
                result = await session.execute(
                    select(func.count(MessageState.id))
                    .where(and_(
                        MessageState.status == ProcessingStatus.COMPLETED,
                        MessageState.processing_completed_at >= last_24h
                    ))
                )
                processed_last_24h = result.scalar() or 0
                
                # Failed messages in last hour
                result = await session.execute(
                    select(func.count(MessageState.id))
                    .where(and_(
                        MessageState.status == ProcessingStatus.FAILED,
                        MessageState.updated_at >= last_hour
                    ))
                )
                failed_last_hour = result.scalar() or 0
                
                # Processing queue size (pending messages)
                result = await session.execute(
                    select(func.count(MessageState.id))
                    .where(MessageState.status.in_([
                        ProcessingStatus.RECEIVED,
                        ProcessingStatus.PARSING,
                        ProcessingStatus.CLASSIFYING,
                        ProcessingStatus.CREATING_TICKET,
                        ProcessingStatus.SENDING_CONFIRMATION,
                        ProcessingStatus.SCHEDULING_ESCALATION
                    ]))
                )
                queue_size = result.scalar() or 0
                
                # Average processing time (last 100 completed messages)
                result = await session.execute(
                    select(MessageState)
                    .where(and_(
                        MessageState.status == ProcessingStatus.COMPLETED,
                        MessageState.processing_started_at.isnot(None),
                        MessageState.processing_completed_at.isnot(None)
                    ))
                    .order_by(MessageState.processing_completed_at.desc())
                    .limit(100)
                )
                recent_completed = result.scalars().all()
                
                avg_processing_time = 0
                if recent_completed:
                    total_time = sum(
                        (msg.processing_completed_at - msg.processing_started_at).total_seconds()
                        for msg in recent_completed
                        if msg.processing_started_at and msg.processing_completed_at
                    )
                    avg_processing_time = total_time / len(recent_completed)
                
                return {
                    "processed_last_hour": processed_last_hour,
                    "processed_last_24h": processed_last_24h,
                    "failed_last_hour": failed_last_hour,
                    "current_queue_size": queue_size,
                    "avg_processing_time_seconds": round(avg_processing_time, 2),
                    "success_rate_last_hour": round(
                        (processed_last_hour / (processed_last_hour + failed_last_hour) * 100)
                        if (processed_last_hour + failed_last_hour) > 0 else 100, 2
                    )
                }
                
        except Exception as e:
            logger.error("Error getting processing metrics", error=str(e))
            return {"error": str(e)}
    
    async def _generate_alerts(self, health_status: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on health status."""
        alerts = []
        
        try:
            # Check for critical component failures
            for component_name, component_health in health_status["components"].items():
                if component_health["status"] == "critical":
                    alerts.append({
                        "level": "critical",
                        "component": component_name,
                        "message": f"{component_name.title()} is down",
                        "details": component_health.get("error", "Unknown error")
                    })
                elif component_health["status"] == "degraded":
                    alerts.append({
                        "level": "warning",
                        "component": component_name,
                        "message": f"{component_name.title()} is degraded",
                        "details": component_health.get("error", "Performance issues")
                    })
            
            # Check system resource alerts
            metrics = health_status.get("metrics", {})
            
            # CPU usage alert
            cpu_usage = metrics.get("cpu", {}).get("usage_percent", 0)
            if cpu_usage > 90:
                alerts.append({
                    "level": "critical",
                    "component": "system",
                    "message": f"High CPU usage: {cpu_usage}%",
                    "details": "CPU usage is critically high"
                })
            elif cpu_usage > 80:
                alerts.append({
                    "level": "warning",
                    "component": "system",
                    "message": f"Elevated CPU usage: {cpu_usage}%",
                    "details": "CPU usage is higher than normal"
                })
            
            # Memory usage alert
            memory_usage = metrics.get("memory", {}).get("usage_percent", 0)
            if memory_usage > 90:
                alerts.append({
                    "level": "critical",
                    "component": "system",
                    "message": f"High memory usage: {memory_usage}%",
                    "details": "Memory usage is critically high"
                })
            elif memory_usage > 85:
                alerts.append({
                    "level": "warning",
                    "component": "system",
                    "message": f"Elevated memory usage: {memory_usage}%",
                    "details": "Memory usage is higher than normal"
                })
            
            # Processing alerts
            processing = metrics.get("processing", {})
            
            # High failure rate
            success_rate = processing.get("success_rate_last_hour", 100)
            if success_rate < 95:
                alerts.append({
                    "level": "warning" if success_rate > 80 else "critical",
                    "component": "processing",
                    "message": f"Low processing success rate: {success_rate}%",
                    "details": f"Processing success rate has dropped to {success_rate}%"
                })
            
            # Large processing queue
            queue_size = processing.get("current_queue_size", 0)
            if queue_size > 100:
                alerts.append({
                    "level": "warning" if queue_size < 500 else "critical",
                    "component": "processing",
                    "message": f"Large processing queue: {queue_size} messages",
                    "details": f"Processing queue has {queue_size} pending messages"
                })
            
            # Slow processing
            avg_time = processing.get("avg_processing_time_seconds", 0)
            if avg_time > 300:  # 5 minutes
                alerts.append({
                    "level": "warning",
                    "component": "processing",
                    "message": f"Slow processing: {avg_time:.1f}s average",
                    "details": f"Average processing time is {avg_time:.1f} seconds"
                })
            
        except Exception as e:
            logger.error("Error generating alerts", error=str(e))
            alerts.append({
                "level": "critical",
                "component": "monitoring",
                "message": "Alert generation failed",
                "details": str(e)
            })
        
        return alerts
    
    async def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics over specified time period."""
        try:
            async with get_db_session() as session:
                start_time = datetime.utcnow() - timedelta(hours=hours)
                
                # Ticket creation over time (hourly buckets)
                ticket_creation_query = text("""
                    SELECT 
                        date_trunc('hour', created_at) as hour,
                        COUNT(*) as count
                    FROM tickets 
                    WHERE created_at >= :start_time
                    GROUP BY date_trunc('hour', created_at)
                    ORDER BY hour
                """)
                
                result = await session.execute(ticket_creation_query, {"start_time": start_time})
                ticket_creation = [
                    {"hour": row.hour.isoformat(), "count": row.count}
                    for row in result
                ]
                
                # Processing performance over time
                processing_query = text("""
                    SELECT 
                        date_trunc('hour', processing_completed_at) as hour,
                        status,
                        COUNT(*) as count,
                        AVG(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at))) as avg_duration
                    FROM message_states 
                    WHERE processing_completed_at >= :start_time
                    GROUP BY date_trunc('hour', processing_completed_at), status
                    ORDER BY hour
                """)
                
                result = await session.execute(processing_query, {"start_time": start_time})
                processing_performance = []
                for row in result:
                    processing_performance.append({
                        "hour": row.hour.isoformat(),
                        "status": row.status,
                        "count": row.count,
                        "avg_duration_seconds": round(row.avg_duration or 0, 2)
                    })
                
                return {
                    "period_hours": hours,
                    "start_time": start_time.isoformat(),
                    "ticket_creation_by_hour": ticket_creation,
                    "processing_performance_by_hour": processing_performance
                }
                
        except Exception as e:
            logger.error("Error getting performance metrics", error=str(e))
            raise
    
    async def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history (placeholder - would typically store in database)."""
        # In a real implementation, you'd store alerts in a database table
        # For now, return current alerts
        health_status = await self.get_system_health()
        alerts = health_status.get("alerts", [])
        
        # Add timestamp to each alert
        for alert in alerts:
            alert["timestamp"] = datetime.utcnow().isoformat()
        
        return alerts