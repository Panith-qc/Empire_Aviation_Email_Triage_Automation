"""Reporting service for generating monthly and custom reports."""

import asyncio
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db_session
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketCategory
from app.models.activity import ActivityLog, ActivityType
from app.models.escalation import EscalationStep, EscalationStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReportingService:
    """Service for generating reports and analytics."""
    
    async def generate_monthly_report(
        self, 
        year: int, 
        month: int,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Generate comprehensive monthly report."""
        try:
            # Calculate date range
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            
            async with get_db_session() as session:
                # Get ticket statistics
                ticket_stats = await self._get_ticket_statistics(session, start_date, end_date)
                
                # Get SLA performance
                sla_performance = await self._get_sla_performance(session, start_date, end_date)
                
                # Get escalation statistics
                escalation_stats = await self._get_escalation_statistics(session, start_date, end_date)
                
                # Get category breakdown
                category_breakdown = await self._get_category_breakdown(session, start_date, end_date)
                
                # Get top customers
                top_customers = await self._get_top_customers(session, start_date, end_date)
                
                # Get response time analytics
                response_times = await self._get_response_time_analytics(session, start_date, end_date)
                
                report = {
                    "report_info": {
                        "type": "monthly_report",
                        "period": f"{year}-{month:02d}",
                        "generated_at": datetime.utcnow().isoformat(),
                        "date_range": {
                            "start": start_date.isoformat(),
                            "end": end_date.isoformat()
                        }
                    },
                    "summary": ticket_stats,
                    "sla_performance": sla_performance,
                    "escalations": escalation_stats,
                    "categories": category_breakdown,
                    "top_customers": top_customers,
                    "response_times": response_times
                }
                
                if format == "csv":
                    return await self._convert_to_csv(report)
                
                return report
                
        except Exception as e:
            logger.error("Error generating monthly report", 
                        year=year, month=month, error=str(e))
            raise
    
    async def _get_ticket_statistics(
        self, 
        session: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get basic ticket statistics."""
        # Total tickets created
        result = await session.execute(
            select(func.count(Ticket.id))
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
        )
        total_created = result.scalar() or 0
        
        # Tickets by status
        result = await session.execute(
            select(Ticket.status, func.count(Ticket.id))
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
            .group_by(Ticket.status)
        )
        status_counts = {status.value: count for status, count in result.all()}
        
        # Tickets by priority
        result = await session.execute(
            select(Ticket.priority, func.count(Ticket.id))
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
            .group_by(Ticket.priority)
        )
        priority_counts = {priority.value: count for priority, count in result.all()}
        
        # Resolution rate
        resolved_count = status_counts.get("resolved", 0) + status_counts.get("closed", 0)
        resolution_rate = (resolved_count / total_created * 100) if total_created > 0 else 0
        
        return {
            "total_tickets": total_created,
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "resolution_rate_percent": round(resolution_rate, 2),
            "resolved_tickets": resolved_count
        }
    
    async def _get_sla_performance(
        self, 
        session: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get SLA performance metrics."""
        # Response SLA performance
        result = await session.execute(
            select(Ticket)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date,
                Ticket.first_response_at.isnot(None)
            ))
        )
        responded_tickets = result.scalars().all()
        
        response_sla_met = 0
        total_response_time_minutes = 0
        
        for ticket in responded_tickets:
            if ticket.response_due_at and ticket.first_response_at:
                if ticket.first_response_at <= ticket.response_due_at:
                    response_sla_met += 1
                
                response_time = (ticket.first_response_at - ticket.created_at).total_seconds() / 60
                total_response_time_minutes += response_time
        
        response_sla_rate = (response_sla_met / len(responded_tickets) * 100) if responded_tickets else 0
        avg_response_time = total_response_time_minutes / len(responded_tickets) if responded_tickets else 0
        
        # Resolution SLA performance
        result = await session.execute(
            select(Ticket)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date,
                Ticket.resolved_at.isnot(None)
            ))
        )
        resolved_tickets = result.scalars().all()
        
        resolution_sla_met = 0
        total_resolution_time_hours = 0
        
        for ticket in resolved_tickets:
            if ticket.resolution_due_at and ticket.resolved_at:
                if ticket.resolved_at <= ticket.resolution_due_at:
                    resolution_sla_met += 1
                
                resolution_time = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                total_resolution_time_hours += resolution_time
        
        resolution_sla_rate = (resolution_sla_met / len(resolved_tickets) * 100) if resolved_tickets else 0
        avg_resolution_time = total_resolution_time_hours / len(resolved_tickets) if resolved_tickets else 0
        
        return {
            "response_sla": {
                "tickets_with_response": len(responded_tickets),
                "sla_met_count": response_sla_met,
                "sla_rate_percent": round(response_sla_rate, 2),
                "average_response_time_minutes": round(avg_response_time, 2)
            },
            "resolution_sla": {
                "resolved_tickets": len(resolved_tickets),
                "sla_met_count": resolution_sla_met,
                "sla_rate_percent": round(resolution_sla_rate, 2),
                "average_resolution_time_hours": round(avg_resolution_time, 2)
            }
        }
    
    async def _get_escalation_statistics(
        self, 
        session: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get escalation statistics."""
        # Tickets with escalations
        result = await session.execute(
            select(func.count(Ticket.id.distinct()))
            .join(EscalationStep, Ticket.id == EscalationStep.ticket_id)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
        )
        tickets_escalated = result.scalar() or 0
        
        # Total escalation steps
        result = await session.execute(
            select(func.count(EscalationStep.id))
            .join(Ticket, EscalationStep.ticket_id == Ticket.id)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
        )
        total_escalation_steps = result.scalar() or 0
        
        # Escalations by status
        result = await session.execute(
            select(EscalationStep.status, func.count(EscalationStep.id))
            .join(Ticket, EscalationStep.ticket_id == Ticket.id)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
            .group_by(EscalationStep.status)
        )
        escalation_status_counts = {status.value: count for status, count in result.all()}
        
        # Escalations by channel
        result = await session.execute(
            select(EscalationStep.channel, func.count(EscalationStep.id))
            .join(Ticket, EscalationStep.ticket_id == Ticket.id)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
            .group_by(EscalationStep.channel)
        )
        escalation_channel_counts = {channel.value: count for channel, count in result.all()}
        
        return {
            "tickets_escalated": tickets_escalated,
            "total_escalation_steps": total_escalation_steps,
            "escalation_status_breakdown": escalation_status_counts,
            "escalation_channel_breakdown": escalation_channel_counts
        }
    
    async def _get_category_breakdown(
        self, 
        session: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get ticket category breakdown."""
        result = await session.execute(
            select(Ticket.category, func.count(Ticket.id))
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
            .group_by(Ticket.category)
        )
        
        category_counts = {}
        for category, count in result.all():
            category_counts[category.value] = count
        
        return category_counts
    
    async def _get_top_customers(
        self, 
        session: AsyncSession, 
        start_date: datetime, 
        end_date: datetime,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top customers by ticket count."""
        result = await session.execute(
            select(
                Ticket.customer_email,
                Ticket.customer_name,
                func.count(Ticket.id).label('ticket_count')
            )
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ))
            .group_by(Ticket.customer_email, Ticket.customer_name)
            .order_by(func.count(Ticket.id).desc())
            .limit(limit)
        )
        
        top_customers = []
        for customer_email, customer_name, ticket_count in result.all():
            top_customers.append({
                "customer_email": customer_email,
                "customer_name": customer_name or "Unknown",
                "ticket_count": ticket_count
            })
        
        return top_customers
    
    async def _get_response_time_analytics(
        self, 
        session: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get response time analytics by priority."""
        result = await session.execute(
            select(Ticket)
            .where(and_(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date,
                Ticket.first_response_at.isnot(None)
            ))
        )
        
        tickets = result.scalars().all()
        
        priority_response_times = {}
        
        for ticket in tickets:
            priority = ticket.priority.value
            if priority not in priority_response_times:
                priority_response_times[priority] = []
            
            response_time_minutes = (ticket.first_response_at - ticket.created_at).total_seconds() / 60
            priority_response_times[priority].append(response_time_minutes)
        
        # Calculate statistics for each priority
        analytics = {}
        for priority, times in priority_response_times.items():
            if times:
                analytics[priority] = {
                    "count": len(times),
                    "average_minutes": round(sum(times) / len(times), 2),
                    "min_minutes": round(min(times), 2),
                    "max_minutes": round(max(times), 2),
                    "median_minutes": round(sorted(times)[len(times)//2], 2)
                }
        
        return analytics
    
    async def _convert_to_csv(self, report: Dict[str, Any]) -> str:
        """Convert report to CSV format."""
        output = io.StringIO()
        
        # Write summary section
        output.write("Embassy Aviation Monthly Report\n")
        output.write(f"Period: {report['report_info']['period']}\n")
        output.write(f"Generated: {report['report_info']['generated_at']}\n\n")
        
        # Write ticket summary
        output.write("TICKET SUMMARY\n")
        summary = report['summary']
        output.write(f"Total Tickets,{summary['total_tickets']}\n")
        output.write(f"Resolution Rate,{summary['resolution_rate_percent']}%\n")
        output.write(f"Resolved Tickets,{summary['resolved_tickets']}\n\n")
        
        # Write status breakdown
        output.write("STATUS BREAKDOWN\n")
        for status, count in summary['status_breakdown'].items():
            output.write(f"{status.title()},{count}\n")
        output.write("\n")
        
        # Write priority breakdown
        output.write("PRIORITY BREAKDOWN\n")
        for priority, count in summary['priority_breakdown'].items():
            output.write(f"{priority.title()},{count}\n")
        output.write("\n")
        
        # Write SLA performance
        output.write("SLA PERFORMANCE\n")
        sla = report['sla_performance']
        output.write(f"Response SLA Rate,{sla['response_sla']['sla_rate_percent']}%\n")
        output.write(f"Average Response Time,{sla['response_sla']['average_response_time_minutes']} minutes\n")
        output.write(f"Resolution SLA Rate,{sla['resolution_sla']['sla_rate_percent']}%\n")
        output.write(f"Average Resolution Time,{sla['resolution_sla']['average_resolution_time_hours']} hours\n\n")
        
        # Write top customers
        output.write("TOP CUSTOMERS\n")
        output.write("Email,Name,Ticket Count\n")
        for customer in report['top_customers']:
            output.write(f"{customer['customer_email']},{customer['customer_name']},{customer['ticket_count']}\n")
        
        return output.getvalue()
    
    async def get_ticket_details_report(
        self,
        start_date: datetime,
        end_date: datetime,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get detailed ticket report with filters."""
        try:
            async with get_db_session() as session:
                query = select(Ticket).where(and_(
                    Ticket.created_at >= start_date,
                    Ticket.created_at < end_date
                ))
                
                # Apply filters
                if category:
                    query = query.where(Ticket.category == TicketCategory(category))
                if priority:
                    query = query.where(Ticket.priority == TicketPriority(priority))
                if status:
                    query = query.where(Ticket.status == TicketStatus(status))
                
                result = await session.execute(query.order_by(Ticket.created_at.desc()))
                tickets = result.scalars().all()
                
                ticket_details = []
                for ticket in tickets:
                    # Calculate response time
                    response_time_minutes = None
                    if ticket.first_response_at:
                        response_time_minutes = (ticket.first_response_at - ticket.created_at).total_seconds() / 60
                    
                    # Calculate resolution time
                    resolution_time_hours = None
                    if ticket.resolved_at:
                        resolution_time_hours = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                    
                    ticket_details.append({
                        "ticket_number": ticket.ticket_number,
                        "created_at": ticket.created_at.isoformat(),
                        "title": ticket.title,
                        "category": ticket.category.value,
                        "priority": ticket.priority.value,
                        "status": ticket.status.value,
                        "customer_email": ticket.customer_email,
                        "customer_name": ticket.customer_name,
                        "aircraft_registration": ticket.aircraft_registration,
                        "response_time_minutes": round(response_time_minutes, 2) if response_time_minutes else None,
                        "resolution_time_hours": round(resolution_time_hours, 2) if resolution_time_hours else None,
                        "escalation_level": ticket.escalation_level,
                        "escalation_stopped": ticket.escalation_stopped
                    })
                
                return ticket_details
                
        except Exception as e:
            logger.error("Error generating ticket details report", error=str(e))
            raise
    
    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get real-time dashboard metrics."""
        try:
            async with get_db_session() as session:
                now = datetime.utcnow()
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                this_week = today - timedelta(days=today.weekday())
                this_month = today.replace(day=1)
                
                # Today's metrics
                result = await session.execute(
                    select(func.count(Ticket.id))
                    .where(Ticket.created_at >= today)
                )
                tickets_today = result.scalar() or 0
                
                # This week's metrics
                result = await session.execute(
                    select(func.count(Ticket.id))
                    .where(Ticket.created_at >= this_week)
                )
                tickets_this_week = result.scalar() or 0
                
                # This month's metrics
                result = await session.execute(
                    select(func.count(Ticket.id))
                    .where(Ticket.created_at >= this_month)
                )
                tickets_this_month = result.scalar() or 0
                
                # Open tickets by priority
                result = await session.execute(
                    select(Ticket.priority, func.count(Ticket.id))
                    .where(Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED]))
                    .group_by(Ticket.priority)
                )
                open_by_priority = {priority.value: count for priority, count in result.all()}
                
                # Overdue tickets
                result = await session.execute(
                    select(func.count(Ticket.id))
                    .where(and_(
                        Ticket.response_due_at < now,
                        Ticket.first_response_at.is_(None),
                        Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED])
                    ))
                )
                overdue_response = result.scalar() or 0
                
                # Active escalations
                result = await session.execute(
                    select(func.count(Ticket.id.distinct()))
                    .join(EscalationStep, Ticket.id == EscalationStep.ticket_id)
                    .where(and_(
                        Ticket.escalation_stopped == False,
                        EscalationStep.status.in_([EscalationStatus.PENDING, EscalationStatus.SCHEDULED])
                    ))
                )
                active_escalations = result.scalar() or 0
                
                return {
                    "period_metrics": {
                        "today": tickets_today,
                        "this_week": tickets_this_week,
                        "this_month": tickets_this_month
                    },
                    "open_tickets_by_priority": open_by_priority,
                    "overdue_response_tickets": overdue_response,
                    "active_escalations": active_escalations,
                    "last_updated": now.isoformat()
                }
                
        except Exception as e:
            logger.error("Error getting dashboard metrics", error=str(e))
            raise