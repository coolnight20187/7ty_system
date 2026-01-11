from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
import pandas as pd
import json
import os
import shutil
import zipfile
from pathlib import Path

from database import get_db
from models import (
    User, Agent, Bill, Transaction, Customer, 
    ActivityLog, SystemConfig, FileUpload,
    UserRole, BillStatus, TransactionStatus, AgentStatus
)
from schemas import (
    DashboardResponse,
    DashboardStats,
    SalesChartData,
    BillsChartData,
    RecentActivity,
    TopAgent,
    ReportRequest,
    ReportResponse,
    SalesReportItem,
    AgentReportItem,
    SystemReportItem,
    DateRange,
    SystemConfigResponse,
    SystemConfigUpdate,
    PaginatedResponse,
    PaginationParams,
    SuccessResponse,
    ErrorResponse,
    HealthCheckResponse,
    BackupRequest,
    BackupResponse,
    ImportResponse,
    ApiSystemStatus
)
from dependencies import get_current_active_admin, get_current_active_user
from utils import (
    generate_report,
    export_to_excel,
    export_to_csv,
    backup_database,
    restore_database,
    get_system_info,
    format_currency
)
from services.email_service import send_system_notification
from config import settings

router = APIRouter(tags=["system"])

# Helper function for date formatting (SQLite vs PostgreSQL)
def date_format_func(column, format_str):
    """
    Create date format expression compatible with both SQLite and PostgreSQL.
    SQLite uses strftime, PostgreSQL uses to_char.
    """
    # Check if using SQLite
    if settings.DATABASE_TYPE == "sqlite":
        # Convert PostgreSQL format to SQLite strftime format
        sqlite_format = format_str.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('WW', '%W')
        return func.strftime(sqlite_format, column)
    else:
        # PostgreSQL
        return func.to_char(column, format_str)

# ==================== DASHBOARD ENDPOINTS ====================

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_stats(
    period: str = Query("today", regex="^(today|week|month|year|custom)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy thống kê tổng quan dashboard
    """
    try:
        today = datetime.now().date()
        # Khởi tạo sẵn month_ago để tránh lỗi undefined variable
        month_ago = today - timedelta(days=30)
        
        # Xác định khoảng thời gian
        if period == "today":
            date_filter = func.date(Bill.created_at) == today
            trans_date_filter = func.date(Transaction.created_at) == today
        elif period == "week":
            week_ago = today - timedelta(days=7)
            date_filter = func.date(Bill.created_at) >= week_ago
            trans_date_filter = func.date(Transaction.created_at) >= week_ago
        elif period == "month":
            month_ago = today - timedelta(days=30)
            date_filter = func.date(Bill.created_at) >= month_ago
            trans_date_filter = func.date(Transaction.created_at) >= month_ago
        elif period == "year":
            year_ago = today - timedelta(days=365)
            date_filter = func.date(Bill.created_at) >= year_ago
            trans_date_filter = func.date(Transaction.created_at) >= year_ago
        elif period == "custom" and start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_filter = and_(
                    func.date(Bill.created_at) >= start,
                    func.date(Bill.created_at) <= end
                )
                trans_date_filter = and_(
                    func.date(Transaction.created_at) >= start,
                    func.date(Transaction.created_at) <= end
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ngày không đúng định dạng (YYYY-MM-DD)"
                )
        else:
            date_filter = func.date(Bill.created_at) == today
            trans_date_filter = func.date(Transaction.created_at) == today
        
        # Thống kê cơ bản
        total_agents = db.query(func.count(Agent.id)).scalar() or 0
        total_customers = db.query(func.count(Customer.id)).scalar() or 0
        total_bills = db.query(func.count(Bill.id)).scalar() or 0
        total_transactions = db.query(func.count(Transaction.id)).scalar() or 0
        
        # Thống kê hôm nay
        today_revenue = db.query(
            func.sum(Transaction.amount)
        ).filter(
            and_(
                func.date(Transaction.created_at) == today,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        today_transactions = db.query(
            func.count(Transaction.id)
        ).filter(
            and_(
                func.date(Transaction.created_at) == today,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        # Thống kê pending
        pending_agents = db.query(
            func.count(Agent.id)
        ).filter(Agent.status == AgentStatus.PENDING).scalar() or 0
        
        pending_bills = db.query(
            func.count(Bill.id)
        ).filter(Bill.status == BillStatus.IN_STOCK).scalar() or 0
        
        # Hóa đơn quá hạn
        overdue_bills = db.query(
            func.count(Bill.id)
        ).filter(
            and_(
                Bill.due_date < today,
                Bill.status.in_([BillStatus.IN_STOCK, BillStatus.PENDING])
            )
        ).scalar() or 0
        
        # Tính trends (so sánh với ngày hôm qua)
        yesterday = today - timedelta(days=1)
        
        # Agent trend
        agents_today = total_agents
        agents_yesterday = db.query(
            func.count(Agent.id)
        ).filter(func.date(Agent.created_at) == yesterday).scalar() or 0
        
        agent_trend = {
            "value": ((agents_today - agents_yesterday) / agents_yesterday * 100) if agents_yesterday > 0 else 0,
            "period": "hôm qua"
        }
        
        # Bill trend
        bills_today = db.query(
            func.count(Bill.id)
        ).filter(func.date(Bill.created_at) == today).scalar() or 0
        
        bills_yesterday = db.query(
            func.count(Bill.id)
        ).filter(func.date(Bill.created_at) == yesterday).scalar() or 0
        
        bill_trend = {
            "value": ((bills_today - bills_yesterday) / bills_yesterday * 100) if bills_yesterday > 0 else 0,
            "period": "hôm qua"
        }
        
        # Revenue trend
        revenue_yesterday = db.query(
            func.sum(Transaction.amount)
        ).filter(
            and_(
                func.date(Transaction.created_at) == yesterday,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        revenue_trend = {
            "value": ((today_revenue - revenue_yesterday) / revenue_yesterday * 100) if revenue_yesterday > 0 else 0,
            "period": "hôm qua"
        }
        
        # Transaction trend
        trans_yesterday = db.query(
            func.count(Transaction.id)
        ).filter(
            and_(
                func.date(Transaction.created_at) == yesterday,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        transaction_trend = {
            "value": ((today_transactions - trans_yesterday) / trans_yesterday * 100) if trans_yesterday > 0 else 0,
            "period": "hôm qua"
        }
        
        # Tạo stats object
        stats = DashboardStats(
            total_agents=total_agents,
            total_customers=total_customers,
            total_bills=total_bills,
            total_transactions=total_transactions,
            today_revenue=float(today_revenue),
            today_transactions=today_transactions,
            pending_agents=pending_agents,
            pending_bills=pending_bills,
            overdue_bills=overdue_bills,
            agent_trend=agent_trend,
            bill_trend=bill_trend,
            revenue_trend=revenue_trend,
            transaction_trend=transaction_trend
        )
        
        # Lấy dữ liệu biểu đồ doanh số 12 tháng gần nhất
        twelve_months_ago = today - timedelta(days=365)
        
        sales_data = db.query(
            date_format_func(Bill.created_at, 'YYYY-MM').label('month'),
            func.sum(Bill.total_amount).label('total_amount'),
            func.count(Bill.id).label('bill_count')
        ).filter(
            and_(
                Bill.created_at >= twelve_months_ago,
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
            )
        ).group_by(date_format_func(Bill.created_at, 'YYYY-MM')).order_by(date_format_func(Bill.created_at, 'YYYY-MM')).all()
        
        sales_chart = [
            SalesChartData(
                date=item.month,
                amount=item.total_amount or 0,
                count=item.bill_count
            )
            for item in sales_data
        ]
        
        # Lấy dữ liệu biểu đồ phân loại hóa đơn
        bills_by_status = db.query(
            Bill.status,
            func.count(Bill.id).label('count'),
            func.sum(Bill.total_amount).label('total_amount')
        ).group_by(Bill.status).all()
        
        bills_chart = [
            BillsChartData(
                status=item.status.value,
                count=item.count,
                amount=item.total_amount or 0
            )
            for item in bills_by_status
        ]
        
        # Lấy hoạt động gần đây
        recent_activities = db.query(ActivityLog).join(User).order_by(
            ActivityLog.created_at.desc()
        ).limit(10).all()
        
        recent_activity_list = []
        for activity in recent_activities:
            recent_activity_list.append(
                RecentActivity(
                    id=activity.id,
                    type=activity.activity_type,
                    description=activity.details or activity.action or "",
                    timestamp=activity.created_at,
                    user_id=activity.user_id
                )
            )
        
        # Lấy top đại lý
        top_agents_query = db.query(
            Agent.id,
            Agent.agent_code,
            User.full_name,
            func.sum(Bill.total_amount).label('total_sales'),
            func.count(Bill.id).label('bill_count')
        ).join(User, Agent.user_id == User.id).join(
            Bill, Agent.id == Bill.agent_id
        ).filter(
            and_(
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID]),
                Bill.created_at >= month_ago
            )
        ).group_by(Agent.id, Agent.agent_code, User.full_name).order_by(
            func.sum(Bill.total_amount).desc()
        ).limit(5).all()
        
        top_agent_list = []
        for agent in top_agents_query:
            total_success = db.query(
                func.count(Bill.id)
            ).filter(
                and_(
                    Bill.agent_id == agent.id,
                    Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
                )
            ).scalar() or 0
            
            total_all = db.query(
                func.count(Bill.id)
            ).filter(
                Bill.agent_id == agent.id
            ).scalar() or 0
            
            success_rate = (total_success / total_all * 100) if total_all > 0 else 0
            
            top_agent_list.append(
                TopAgent(
                    id=agent.id,
                    full_name=agent.full_name,
                    agent_code=agent.agent_code,
                    total_sales=float(agent.total_sales or 0),
                    bill_count=agent.bill_count or 0,
                    success_rate=success_rate
                )
            )
        
        return DashboardResponse(
            stats=stats,
            sales_data=sales_chart,
            bills_data=bills_chart,
            recent_activities=recent_activity_list,
            top_agents=top_agent_list
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy thống kê dashboard: {str(e)}"
        )

# ==================== REPORT ENDPOINTS ====================

@router.post("/reports/sales", response_model=ReportResponse)
async def generate_sales_report(
    report_request: ReportRequest,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Tạo báo cáo doanh thu
    """
    try:
        # Validate date range
        if report_request.start_date > report_request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ngày bắt đầu phải nhỏ hơn ngày kết thúc"
            )
        
        # Xác định group by
        group_by_format = "%Y-%m-%d"  # default daily
        if report_request.group_by == "week":
            group_by_format = "YYYY-WW"
        elif report_request.group_by == "month":
            group_by_format = "YYYY-MM"
        elif report_request.group_by == "year":
            group_by_format = "YYYY"
        
        # Query dữ liệu
        query = db.query(
            date_format_func(Bill.created_at, group_by_format).label('period'),
            func.sum(Bill.total_amount).label('total_amount'),
            func.count(Bill.id).label('total_bills'),
            func.sum(Agent.commission_rate * Bill.total_amount / 100).label('total_commission')
        ).join(Agent, Bill.agent_id == Agent.id).filter(
            and_(
                Bill.created_at >= report_request.start_date,
                Bill.created_at <= report_request.end_date,
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
            )
        )
        
        # Lọc theo agent
        if report_request.agent_id:
            query = query.filter(Bill.agent_id == report_request.agent_id)
        
        # Lọc theo status
        if report_request.status:
            query = query.filter(Bill.status == report_request.status)
        
        # Group và order
        data = query.group_by(date_format_func(Bill.created_at, group_by_format)).order_by(date_format_func(Bill.created_at, group_by_format)).all()
        
        # Tạo danh sách items
        items = []
        for item in data:
            items.append(
                SalesReportItem(
                    period=item.period,
                    total_amount=float(item.total_amount or 0),
                    total_bills=item.total_bills or 0,
                    total_commission=float(item.total_commission or 0),
                    avg_amount=float((item.total_amount or 0) / (item.total_bills or 1))
                )
            )
        
        # Tính tổng
        total_amount = sum(item.total_amount for item in items)
        total_bills = sum(item.total_bills for item in items)
        total_commission = sum(item.total_commission for item in items)
        
        return ReportResponse(
            success=True,
            report_type="sales",
            date_range=DateRange(
                start_date=report_request.start_date,
                end_date=report_request.end_date
            ),
            total_amount=total_amount,
            total_bills=total_bills,
            total_commission=total_commission,
            items=items,
            summary={
                "avg_daily_sales": total_amount / max((report_request.end_date - report_request.start_date).days, 1),
                "avg_bill_amount": total_amount / total_bills if total_bills > 0 else 0,
                "commission_rate": (total_commission / total_amount * 100) if total_amount > 0 else 0
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo báo cáo doanh thu: {str(e)}"
        )

@router.post("/reports/agents", response_model=ReportResponse)
async def generate_agent_report(
    report_request: ReportRequest,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Tạo báo cáo đại lý
    """
    try:
        # Query dữ liệu đại lý
        query = db.query(
            Agent.id,
            Agent.agent_code,
            User.full_name,
            func.sum(Bill.total_amount).label('total_sales'),
            func.count(Bill.id).label('total_bills'),
            func.sum(Agent.commission_rate * Bill.total_amount / 100).label('total_commission'),
            Agent.commission_rate
        ).join(User, Agent.user_id == User.id).outerjoin(
            Bill, and_(
                Bill.agent_id == Agent.id,
                Bill.created_at >= report_request.start_date,
                Bill.created_at <= report_request.end_date,
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
            )
        )
        
        # Lọc theo status agent
        if report_request.status:
            query = query.filter(Agent.status == report_request.status)
        
        # Group và order
        data = query.group_by(Agent.id).order_by(
            func.sum(Bill.total_amount).desc()
        ).all()
        
        # Tạo danh sách items
        items = []
        for agent in data:
            # Tính tỷ lệ thành công
            success_bills = db.query(
                func.count(Bill.id)
            ).filter(
                and_(
                    Bill.agent_id == agent.id,
                    Bill.created_at >= report_request.start_date,
                    Bill.created_at <= report_request.end_date,
                    Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
                )
            ).scalar() or 0
            
            all_bills = db.query(
                func.count(Bill.id)
            ).filter(
                and_(
                    Bill.agent_id == agent.id,
                    Bill.created_at >= report_request.start_date,
                    Bill.created_at <= report_request.end_date
                )
            ).scalar() or 0
            
            success_rate = (success_bills / all_bills * 100) if all_bills > 0 else 0
            
            items.append(
                AgentReportItem(
                    agent_id=agent.id,
                    agent_code=agent.agent_code,
                    full_name=agent.full_name,
                    total_sales=float(agent.total_sales or 0),
                    total_bills=agent.total_bills or 0,
                    total_commission=float(agent.total_commission or 0),
                    success_rate=success_rate,
                    avg_bill_amount=float((agent.total_sales or 0) / (agent.total_bills or 1))
                )
            )
        
        # Tính tổng
        total_amount = sum(item.total_sales for item in items)
        total_bills = sum(item.total_bills for item in items)
        total_commission = sum(item.total_commission for item in items)
        
        return ReportResponse(
            success=True,
            report_type="agents",
            date_range=DateRange(
                start_date=report_request.start_date,
                end_date=report_request.end_date
            ),
            total_amount=total_amount,
            total_bills=total_bills,
            total_commission=total_commission,
            items=items,
            summary={
                "total_agents": len(items),
                "avg_sales_per_agent": total_amount / len(items) if len(items) > 0 else 0,
                "top_performer": max(items, key=lambda x: x.total_sales).full_name if items else None
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo báo cáo đại lý: {str(e)}"
        )

@router.post("/reports/system", response_model=ReportResponse)
async def generate_system_report(
    report_request: ReportRequest,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Tạo báo cáo hệ thống
    """
    try:
        # Tính toán các chỉ số hệ thống
        items = []
        
        # 1. Tổng số user mới
        new_users = db.query(
            func.count(User.id)
        ).filter(
            and_(
                User.created_at >= report_request.start_date,
                User.created_at <= report_request.end_date
            )
        ).scalar() or 0
        
        # Tính trend so với kỳ trước
        prev_start = report_request.start_date - (report_request.end_date - report_request.start_date) - timedelta(days=1)
        prev_end = report_request.start_date - timedelta(days=1)
        
        prev_new_users = db.query(
            func.count(User.id)
        ).filter(
            and_(
                User.created_at >= prev_start,
                User.created_at <= prev_end
            )
        ).scalar() or 0
        
        user_trend = ((new_users - prev_new_users) / prev_new_users * 100) if prev_new_users > 0 else 0
        
        items.append(
            SystemReportItem(
                metric="new_users",
                value=new_users,
                change=user_trend,
                trend="up" if user_trend > 0 else "down" if user_trend < 0 else "stable"
            )
        )
        
        # 2. Tổng số giao dịch
        total_transactions = db.query(
            func.count(Transaction.id)
        ).filter(
            and_(
                Transaction.created_at >= report_request.start_date,
                Transaction.created_at <= report_request.end_date,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        prev_total_transactions = db.query(
            func.count(Transaction.id)
        ).filter(
            and_(
                Transaction.created_at >= prev_start,
                Transaction.created_at <= prev_end,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        transaction_trend = ((total_transactions - prev_total_transactions) / prev_total_transactions * 100) if prev_total_transactions > 0 else 0
        
        items.append(
            SystemReportItem(
                metric="total_transactions",
                value=total_transactions,
                change=transaction_trend,
                trend="up" if transaction_trend > 0 else "down" if transaction_trend < 0 else "stable"
            )
        )
        
        # 3. Tổng doanh thu
        total_revenue = db.query(
            func.sum(Transaction.amount)
        ).filter(
            and_(
                Transaction.created_at >= report_request.start_date,
                Transaction.created_at <= report_request.end_date,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        prev_total_revenue = db.query(
            func.sum(Transaction.amount)
        ).filter(
            and_(
                Transaction.created_at >= prev_start,
                Transaction.created_at <= prev_end,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        revenue_trend = ((total_revenue - prev_total_revenue) / prev_total_revenue * 100) if prev_total_revenue > 0 else 0
        
        items.append(
            SystemReportItem(
                metric="total_revenue",
                value=float(total_revenue),
                change=revenue_trend,
                trend="up" if revenue_trend > 0 else "down" if revenue_trend < 0 else "stable"
            )
        )
        
        # 4. Tỷ lệ thành công
        successful_bills = db.query(
            func.count(Bill.id)
        ).filter(
            and_(
                Bill.created_at >= report_request.start_date,
                Bill.created_at <= report_request.end_date,
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
            )
        ).scalar() or 0
        
        all_bills = db.query(
            func.count(Bill.id)
        ).filter(
            and_(
                Bill.created_at >= report_request.start_date,
                Bill.created_at <= report_request.end_date
            )
        ).scalar() or 0
        
        success_rate = (successful_bills / all_bills * 100) if all_bills > 0 else 0
        
        prev_successful_bills = db.query(
            func.count(Bill.id)
        ).filter(
            and_(
                Bill.created_at >= prev_start,
                Bill.created_at <= prev_end,
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
            )
        ).scalar() or 0
        
        prev_all_bills = db.query(
            func.count(Bill.id)
        ).filter(
            and_(
                Bill.created_at >= prev_start,
                Bill.created_at <= prev_end
            )
        ).scalar() or 0
        
        prev_success_rate = (prev_successful_bills / prev_all_bills * 100) if prev_all_bills > 0 else 0
        
        success_rate_trend = success_rate - prev_success_rate
        
        items.append(
            SystemReportItem(
                metric="success_rate",
                value=success_rate,
                change=success_rate_trend,
                trend="up" if success_rate_trend > 0 else "down" if success_rate_trend < 0 else "stable"
            )
        )
        
        # 5. Doanh thu trung bình mỗi đại lý
        active_agents = db.query(
            func.count(Agent.id)
        ).filter(
            and_(
                Agent.status == AgentStatus.ACTIVE,
                Agent.created_at <= report_request.end_date
            )
        ).scalar() or 1  # Avoid division by zero
        
        avg_revenue_per_agent = total_revenue / active_agents
        
        prev_active_agents = db.query(
            func.count(Agent.id)
        ).filter(
            and_(
                Agent.status == AgentStatus.ACTIVE,
                Agent.created_at <= prev_end
            )
        ).scalar() or 1
        
        prev_avg_revenue = prev_total_revenue / prev_active_agents
        
        avg_revenue_trend = ((avg_revenue_per_agent - prev_avg_revenue) / prev_avg_revenue * 100) if prev_avg_revenue > 0 else 0
        
        items.append(
            SystemReportItem(
                metric="avg_revenue_per_agent",
                value=float(avg_revenue_per_agent),
                change=avg_revenue_trend,
                trend="up" if avg_revenue_trend > 0 else "down" if avg_revenue_trend < 0 else "stable"
            )
        )
        
        return ReportResponse(
            success=True,
            report_type="system",
            date_range=DateRange(
                start_date=report_request.start_date,
                end_date=report_request.end_date
            ),
            total_amount=float(total_revenue),
            total_bills=all_bills,
            total_commission=0,  # Not applicable for system report
            items=items,
            summary={
                "active_agents": active_agents,
                "success_rate": f"{success_rate:.1f}%",
                "growth_rate": f"{revenue_trend:.1f}%"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo báo cáo hệ thống: {str(e)}"
        )

@router.post("/reports/export")
async def export_report(
    report_type: str = Query(..., regex="^(sales|agents|system)$"),
    format: str = Query("excel", regex="^(excel|csv|pdf)$"),
    report_request: ReportRequest = None,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Xuất báo cáo ra file
    """
    try:
        # Tạo báo cáo dựa trên loại
        if report_type == "sales":
            # Query dữ liệu doanh thu
            query = db.query(
                Bill.bill_code,
                Bill.customer_code,
                Bill.customer_name,
                Bill.period,
                Bill.total_amount,
                Bill.status,
                Agent.agent_code,
                User.full_name.label('agent_name'),
                Bill.created_at
            ).join(Agent, Bill.agent_id == Agent.id).join(
                User, Agent.user_id == User.id
            ).filter(
                and_(
                    Bill.created_at >= report_request.start_date,
                    Bill.created_at <= report_request.end_date,
                    Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
                )
            ).order_by(Bill.created_at.desc())
            
            data = query.all()
            
            # Chuẩn bị dữ liệu cho export
            export_data = []
            for item in data:
                export_data.append({
                    "Mã hóa đơn": item.bill_code,
                    "Mã khách hàng": item.customer_code,
                    "Tên khách hàng": item.customer_name,
                    "Kỳ thanh toán": item.period,
                    "Số tiền": float(item.total_amount),
                    "Trạng thái": item.status,
                    "Mã đại lý": item.agent_code,
                    "Tên đại lý": item.agent_name,
                    "Ngày tạo": item.created_at.strftime("%d/%m/%Y %H:%M")
                })
            
            filename = f"bao_cao_doanh_thu_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        elif report_type == "agents":
            # Query dữ liệu đại lý
            query = db.query(
                Agent.agent_code,
                User.full_name,
                Agent.company_name,
                Agent.phone,
                Agent.email,
                Agent.status,
                func.sum(Bill.total_amount).label('total_sales'),
                func.count(Bill.id).label('total_bills'),
                func.sum(Agent.commission_rate * Bill.total_amount / 100).label('total_commission')
            ).join(User, Agent.user_id == User.id).outerjoin(
                Bill, and_(
                    Bill.agent_id == Agent.id,
                    Bill.created_at >= report_request.start_date,
                    Bill.created_at <= report_request.end_date,
                    Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
                )
            ).group_by(Agent.id).order_by(
                func.sum(Bill.total_amount).desc()
            )
            
            data = query.all()
            
            # Chuẩn bị dữ liệu cho export
            export_data = []
            for agent in data:
                export_data.append({
                    "Mã đại lý": agent.agent_code,
                    "Họ tên": agent.full_name,
                    "Công ty": agent.company_name or "",
                    "Điện thoại": agent.phone,
                    "Email": agent.email or "",
                    "Trạng thái": agent.status,
                    "Tổng doanh thu": float(agent.total_sales or 0),
                    "Tổng hóa đơn": agent.total_bills or 0,
                    "Tổng hoa hồng": float(agent.total_commission or 0)
                })
            
            filename = f"bao_cao_dai_ly_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        else:  # system report
            # Thu thập dữ liệu hệ thống
            export_data = []
            
            # Thống kê user
            total_users = db.query(func.count(User.id)).scalar() or 0
            active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
            
            # Thống kê agent
            total_agents = db.query(func.count(Agent.id)).scalar() or 0
            active_agents = db.query(func.count(Agent.id)).filter(Agent.status == AgentStatus.ACTIVE).scalar() or 0
            
            # Thống kê bill
            total_bills = db.query(func.count(Bill.id)).scalar() or 0
            successful_bills = db.query(func.count(Bill.id)).filter(
                Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
            ).scalar() or 0
            
            # Thống kê transaction
            total_transactions = db.query(func.count(Transaction.id)).scalar() or 0
            completed_transactions = db.query(func.count(Transaction.id)).filter(
                Transaction.status == TransactionStatus.COMPLETED
            ).scalar() or 0
            
            # Tổng doanh thu
            total_revenue = db.query(func.sum(Transaction.amount)).filter(
                Transaction.status == TransactionStatus.COMPLETED
            ).scalar() or 0
            
            export_data.append({
                "Chỉ số": "Người dùng",
                "Tổng số": total_users,
                "Đang hoạt động": active_users,
                "Tỷ lệ": f"{(active_users/total_users*100):.1f}%" if total_users > 0 else "0%"
            })
            
            export_data.append({
                "Chỉ số": "Đại lý",
                "Tổng số": total_agents,
                "Đang hoạt động": active_agents,
                "Tỷ lệ": f"{(active_agents/total_agents*100):.1f}%" if total_agents > 0 else "0%"
            })
            
            export_data.append({
                "Chỉ số": "Hóa đơn",
                "Tổng số": total_bills,
                "Thành công": successful_bills,
                "Tỷ lệ": f"{(successful_bills/total_bills*100):.1f}%" if total_bills > 0 else "0%"
            })
            
            export_data.append({
                "Chỉ số": "Giao dịch",
                "Tổng số": total_transactions,
                "Hoàn thành": completed_transactions,
                "Tỷ lệ": f"{(completed_transactions/total_transactions*100):.1f}%" if total_transactions > 0 else "0%"
            })
            
            export_data.append({
                "Chỉ số": "Doanh thu",
                "Tổng số": f"{format_currency(total_revenue)}",
                "Trung bình/ĐL": f"{format_currency(total_revenue/active_agents)}" if active_agents > 0 else "0",
                "Tỷ lệ thành công": f"{(successful_bills/total_bills*100):.1f}%" if total_bills > 0 else "0%"
            })
            
            filename = f"bao_cao_he_thong_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Xuất file
        if format == "excel":
            file_path = export_to_excel(export_data, filename)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif format == "csv":
            file_path = export_to_csv(export_data, filename)
            content_type = "text/csv"
        else:  # pdf
            # Trong thực tế cần thêm thư viện để export PDF
            file_path = export_to_excel(export_data, filename)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        # Gửi email thông báo
        await send_system_notification(
            to_email=current_user.email,
            subject=f"Báo cáo {report_type} đã được xuất",
            template_name="report_exported.html",
            context={
                "report_type": report_type,
                "filename": filename,
                "export_time": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "user": current_user.full_name
            }
        )
        
        return SuccessResponse(
            success=True,
            message=f"Đã xuất báo cáo {report_type} thành công",
            data={
                "filename": filename,
                "file_path": file_path,
                "format": format,
                "record_count": len(export_data)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xuất báo cáo: {str(e)}"
        )

# ==================== SYSTEM CONFIG ENDPOINTS ====================

@router.get("/configs", response_model=List[SystemConfigResponse])
async def get_system_configs(
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách cấu hình hệ thống
    """
    try:
        query = db.query(SystemConfig)
        
        if category:
            query = query.filter(SystemConfig.category == category)
        
        if is_public is not None:
            query = query.filter(SystemConfig.is_public == is_public)
        
        configs = query.order_by(SystemConfig.category, SystemConfig.key).all()
        
        return configs
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy cấu hình hệ thống: {str(e)}"
        )

@router.get("/configs/{key}", response_model=SystemConfigResponse)
async def get_system_config(
    key: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy cấu hình hệ thống theo key
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cấu hình"
        )
    
    # Kiểm tra quyền truy cập nếu config không public
    if not config.is_public and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập cấu hình này"
        )
    
    return config

@router.put("/configs/{key}", response_model=SystemConfigResponse)
async def update_system_config(
    key: str,
    config_update: SystemConfigUpdate,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Cập nhật cấu hình hệ thống
    """
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy cấu hình"
            )
        
        # Cập nhật giá trị
        update_data = config_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)
        
        config.updated_at = datetime.now()
        config.updated_by_id = current_user.id
        
        db.commit()
        db.refresh(config)
        
        return config
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật cấu hình: {str(e)}"
        )

@router.post("/configs/batch-update", response_model=SuccessResponse)
async def batch_update_configs(
    configs: List[Dict[str, Any]],
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Cập nhật hàng loạt cấu hình hệ thống
    """
    try:
        updated_count = 0
        for config_data in configs:
            config = db.query(SystemConfig).filter(
                SystemConfig.key == config_data.get("key")
            ).first()
            
            if config:
                if "value" in config_data:
                    config.value = config_data["value"]
                if "value_type" in config_data:
                    config.value_type = config_data["value_type"]
                if "description" in config_data:
                    config.description = config_data["description"]
                if "is_public" in config_data:
                    config.is_public = config_data["is_public"]
                
                config.updated_at = datetime.now()
                config.updated_by_id = current_user.id
                updated_count += 1
        
        db.commit()
        
        return SuccessResponse(
            success=True,
            message=f"Đã cập nhật {updated_count} cấu hình"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật hàng loạt cấu hình: {str(e)}"
        )

# ==================== BACKUP & RESTORE ENDPOINTS ====================

@router.post("/backup", response_model=BackupResponse)
async def create_backup(
    backup_request: BackupRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Tạo bản sao lưu hệ thống
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(settings.BACKUP_DIR) / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Sao lưu database
        if backup_request.backup_type in ["database", "full"]:
            db_backup_file = backup_dir / "database.sql"
            await backup_database(str(db_backup_file))
        
        # Sao lưu file uploads
        if backup_request.backup_type in ["files", "full"]:
            uploads_dir = Path(settings.UPLOAD_DIR)
            if uploads_dir.exists():
                shutil.copytree(uploads_dir, backup_dir / "uploads")
        
        # Sao lưu logs
        if backup_request.include_logs:
            logs_dir = Path("logs")
            if logs_dir.exists():
                shutil.copytree(logs_dir, backup_dir / "logs")
        
        # Nén backup nếu cần
        if backup_request.compression:
            zip_filename = f"{settings.BACKUP_DIR}/backup_{timestamp}.zip"
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(backup_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, backup_dir)
                        zipf.write(file_path, arcname)
            
            # Xóa thư mục backup gốc
            shutil.rmtree(backup_dir)
            final_path = zip_filename
        else:
            final_path = str(backup_dir)
        
        # Lưu thông tin backup vào database
        backup_record = FileUpload(
            filename=f"backup_{timestamp}.{'zip' if backup_request.compression else 'sql'}",
            original_filename=f"backup_{timestamp}",
            file_path=final_path,
            file_size=os.path.getsize(final_path),
            mime_type="application/zip" if backup_request.compression else "application/sql",
            upload_type="backup",
            user_id=current_user.id,
            status="completed"
        )
        
        db.add(backup_record)
        db.commit()
        
        # Gửi email thông báo
        background_tasks.add_task(
            send_system_notification,
            to_email=current_user.email,
            subject="Sao lưu hệ thống đã hoàn thành",
            template_name="backup_completed.html",
            context={
                "backup_type": backup_request.backup_type,
                "backup_path": final_path,
                "backup_size": f"{os.path.getsize(final_path) / (1024*1024):.2f} MB",
                "timestamp": timestamp,
                "user": current_user.full_name
            }
        )
        
        return BackupResponse(
            success=True,
            backup_id=backup_record.id,
            backup_path=final_path,
            file_size=os.path.getsize(final_path),
            message="Sao lưu thành công"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo sao lưu: {str(e)}"
        )

@router.post("/restore", response_model=SuccessResponse)
async def restore_backup(
    backup_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Khôi phục hệ thống từ bản sao lưu
    """
    try:
        # Tìm thông tin backup
        backup = db.query(FileUpload).filter(
            FileUpload.id == backup_id,
            FileUpload.upload_type == "backup"
        ).first()
        
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy bản sao lưu"
            )
        
        # Khôi phục database
        if backup.filename.endswith('.zip'):
            # Giải nén
            extract_dir = Path(settings.BACKUP_DIR) / "restore_temp"
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(backup.file_path, 'r') as zipf:
                zipf.extractall(extract_dir)
            
            # Tìm file database
            db_files = list(extract_dir.rglob("*.sql"))
            if db_files:
                await restore_database(str(db_files[0]))
            
            # Khôi phục uploads
            uploads_backup = extract_dir / "uploads"
            if uploads_backup.exists():
                shutil.rmtree(settings.UPLOAD_DIR, ignore_errors=True)
                shutil.copytree(uploads_backup, settings.UPLOAD_DIR)
            
            # Xóa thư mục tạm
            shutil.rmtree(extract_dir)
        else:
            await restore_database(backup.file_path)
        
        # Ghi log khôi phục
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="system",
            action="Khôi phục hệ thống",
            details=f"Khôi phục từ backup {backup.filename}",
            ip_address=None,  # Cần lấy từ request trong middleware
            user_agent=None
        )
        
        db.add(activity)
        db.commit()
        
        # Gửi email thông báo
        background_tasks.add_task(
            send_system_notification,
            to_email=current_user.email,
            subject="Khôi phục hệ thống đã hoàn thành",
            template_name="restore_completed.html",
            context={
                "backup_file": backup.filename,
                "restore_time": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "user": current_user.full_name
            }
        )
        
        return SuccessResponse(
            success=True,
            message="Khôi phục thành công"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi khôi phục: {str(e)}"
        )

@router.get("/backups", response_model=PaginatedResponse)
async def list_backups(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Danh sách các bản sao lưu
    """
    try:
        query = db.query(FileUpload).filter(FileUpload.upload_type == "backup")
        
        total = query.count()
        backups = query.order_by(
            FileUpload.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return PaginatedResponse(
            success=True,
            page=skip // limit + 1,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=backups
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy danh sách sao lưu: {str(e)}"
        )

# ==================== SYSTEM HEALTH ENDPOINTS ====================

@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Kiểm tra tình trạng hệ thống
    """
    try:
        # Kiểm tra database
        db_status = "healthy"
        try:
            db.execute("SELECT 1")
        except Exception:
            db_status = "unhealthy"
        
        # Kiểm tra disk space
        import psutil
        disk_usage = psutil.disk_usage('/')
        
        # Kiểm tra memory
        memory = psutil.virtual_memory()
        
        # Kiểm tra uptime
        uptime = psutil.boot_time()
        
        # Kiểm tra các service
        services = {
            "database": db_status,
            "redis": "healthy",  # Cần tích hợp Redis
            "queue": "healthy",  # Cần tích hợp message queue
            "storage": "healthy",
            "email": "healthy"
        }
        
        return HealthCheckResponse(
            status="healthy" if all(v == "healthy" for v in services.values()) else "degraded",
            timestamp=datetime.now(),
            services=services,
            database={
                "status": db_status,
                "connection_pool": db.bind.pool.status() if hasattr(db.bind, 'pool') else "unknown"
            },
            memory={
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent
            },
            uptime=uptime
        )
        
    except Exception as e:
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            services={"error": str(e)},
            database={"status": "error"},
            memory={"error": "unavailable"},
            uptime=0
        )

@router.get("/status", response_model=ApiSystemStatus)
async def system_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy trạng thái hệ thống
    """
    try:
        # Lấy thông tin hệ thống
        sys_info = get_system_info()
        
        # Lấy thời gian sao lưu gần nhất
        last_backup = db.query(FileUpload).filter(
            FileUpload.upload_type == "backup"
        ).order_by(
            FileUpload.created_at.desc()
        ).first()
        
        # Kiểm tra database
        db_ok = True
        try:
            db.execute("SELECT 1")
        except Exception:
            db_ok = False
        
        return ApiSystemStatus(
            status="online" if db_ok else "offline",
            version=settings.VERSION,
            uptime=sys_info.get("uptime", 0),
            database=db_ok,
            redis=True,  # Cần tích hợp Redis
            queue=True,  # Cần tích hợp message queue
            last_backup=last_backup.created_at.isoformat() if last_backup else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy trạng thái hệ thống: {str(e)}"
        )

@router.get("/metrics")
async def system_metrics(
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Lấy metrics hệ thống
    """
    try:
        import psutil
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Network
        net_io = psutil.net_io_counters()
        
        # Process info
        process = psutil.Process()
        
        # Database metrics
        db_metrics = {
            "connections": 0,  # Cần lấy từ connection pool
            "active_queries": 0,  # Cần query database
            "slow_queries": 0
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "cores": psutil.cpu_count(),
                "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else None
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            },
            "process": {
                "pid": process.pid,
                "memory_percent": process.memory_percent(),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads(),
                "open_files": len(process.open_files())
            },
            "database": db_metrics,
            "application": {
                "version": settings.VERSION,
                "uptime": psutil.boot_time(),
                "requests_processed": 0  # Cần tích hợp metrics từ middleware
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy metrics hệ thống: {str(e)}"
        )

# ==================== SYSTEM MAINTENANCE ENDPOINTS ====================

@router.post("/maintenance/start", response_model=SuccessResponse)
async def start_maintenance(
    duration_minutes: int = Query(60, ge=5, le=1440),
    message: str = "Hệ thống đang bảo trì",
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Bắt đầu chế độ bảo trì
    """
    try:
        # Cập nhật config bảo trì
        maintenance_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_mode"
        ).first()
        
        if not maintenance_config:
            maintenance_config = SystemConfig(
                key="maintenance_mode",
                value="true",
                value_type="boolean",
                category="system",
                description="Chế độ bảo trì hệ thống",
                is_public=True
            )
            db.add(maintenance_config)
        else:
            maintenance_config.value = "true"
        
        # Cấu hình thời gian bảo trì
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        end_time_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_end_time"
        ).first()
        
        if not end_time_config:
            end_time_config = SystemConfig(
                key="maintenance_end_time",
                value=end_time.isoformat(),
                value_type="datetime",
                category="system",
                description="Thời gian kết thúc bảo trì",
                is_public=True
            )
            db.add(end_time_config)
        else:
            end_time_config.value = end_time.isoformat()
        
        # Cấu hình thông báo bảo trì
        message_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_message"
        ).first()
        
        if not message_config:
            message_config = SystemConfig(
                key="maintenance_message",
                value=message,
                value_type="string",
                category="system",
                description="Thông báo bảo trì",
                is_public=True
            )
            db.add(message_config)
        else:
            message_config.value = message
        
        db.commit()
        
        # Gửi thông báo cho tất cả admin
        admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
        for admin in admins:
            await send_system_notification(
                to_email=admin.email,
                subject="Hệ thống đã vào chế độ bảo trì",
                template_name="maintenance_started.html",
                context={
                    "start_time": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "end_time": end_time.strftime("%d/%m/%Y %H:%M"),
                    "duration": duration_minutes,
                    "message": message,
                    "user": current_user.full_name
                }
            )
        
        return SuccessResponse(
            success=True,
            message=f"Đã bắt đầu chế độ bảo trì trong {duration_minutes} phút"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi bắt đầu chế độ bảo trì: {str(e)}"
        )

@router.post("/maintenance/stop", response_model=SuccessResponse)
async def stop_maintenance(
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Kết thúc chế độ bảo trì
    """
    try:
        # Tắt chế độ bảo trì
        maintenance_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_mode"
        ).first()
        
        if maintenance_config:
            maintenance_config.value = "false"
        
        db.commit()
        
        # Gửi thông báo
        await send_system_notification(
            to_email=current_user.email,
            subject="Hệ thống đã thoát chế độ bảo trì",
            template_name="maintenance_ended.html",
            context={
                "end_time": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "user": current_user.full_name
            }
        )
        
        return SuccessResponse(
            success=True,
            message="Đã kết thúc chế độ bảo trì"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi kết thúc chế độ bảo trì: {str(e)}"
        )

@router.get("/maintenance/status")
async def get_maintenance_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy trạng thái chế độ bảo trì
    """
    try:
        maintenance_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_mode"
        ).first()
        
        is_maintenance = maintenance_config and maintenance_config.value == "true"
        
        end_time_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_end_time"
        ).first()
        
        message_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_message"
        ).first()
        
        return {
            "is_maintenance": is_maintenance,
            "end_time": end_time_config.value if end_time_config else None,
            "message": message_config.value if message_config else "Hệ thống đang bảo trì",
            "current_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy trạng thái bảo trì: {str(e)}"
        )

# ==================== SYSTEM LOGS ENDPOINTS ====================

@router.get("/logs/activities", response_model=PaginatedResponse)
async def get_activity_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=1000),
    user_id: Optional[int] = None,
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Lấy nhật ký hoạt động
    """
    try:
        query = db.query(ActivityLog)
        
        # Lọc theo user
        if user_id:
            query = query.filter(ActivityLog.user_id == user_id)
        
        # Lọc theo loại hoạt động
        if activity_type:
            query = query.filter(ActivityLog.activity_type == activity_type)
        
        # Lọc theo thời gian
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(ActivityLog.created_at >= start)
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(ActivityLog.created_at < end)
        
        # Tìm kiếm
        if search:
            query = query.filter(
                or_(
                    ActivityLog.action.ilike(f"%{search}%"),
                    ActivityLog.details.ilike(f"%{search}%")
                )
            )
        
        total = query.count()
        logs = query.order_by(
            ActivityLog.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return PaginatedResponse(
            success=True,
            page=skip // limit + 1,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=logs
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy nhật ký hoạt động: {str(e)}"
        )

@router.delete("/logs/cleanup", response_model=SuccessResponse)
async def cleanup_logs(
    older_than_days: int = Query(90, ge=30, le=365),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Dọn dẹp nhật ký cũ
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        deleted_count = db.query(ActivityLog).filter(
            ActivityLog.created_at < cutoff_date
        ).delete()
        
        db.commit()
        
        return SuccessResponse(
            success=True,
            message=f"Đã xóa {deleted_count} bản ghi nhật ký cũ hơn {older_than_days} ngày"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi dọn dẹp nhật ký: {str(e)}"
        )

@router.get("/logs/export")
async def export_logs(
    start_date: str = Query(..., description="Ngày bắt đầu (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Ngày kết thúc (YYYY-MM-DD)"),
    format: str = Query("csv", regex="^(csv|excel)$"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Xuất nhật ký ra file
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        logs = db.query(ActivityLog).join(User).filter(
            and_(
                ActivityLog.created_at >= start,
                ActivityLog.created_at < end
            )
        ).order_by(ActivityLog.created_at.desc()).all()
        
        # Chuẩn bị dữ liệu
        data = []
        for log in logs:
            data.append({
                "Thời gian": log.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                "Người dùng": log.user.full_name if log.user else "N/A",
                "Loại hoạt động": log.activity_type,
                "Hành động": log.action,
                "Chi tiết": log.details or "",
                "Địa chỉ IP": log.ip_address or "N/A",
                "User Agent": log.user_agent or "N/A"
            })
        
        # Xuất file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"system_logs_{start_date}_to_{end_date}_{timestamp}"
        
        if format == "excel":
            file_path = export_to_excel(data, filename)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_path = export_to_csv(data, filename)
            content_type = "text/csv"
        
        return SuccessResponse(
            success=True,
            message=f"Đã xuất {len(logs)} bản ghi nhật ký",
            data={
                "filename": filename,
                "file_path": file_path,
                "format": format,
                "record_count": len(logs)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xuất nhật ký: {str(e)}"
        )


# ==================== DAILYSHOPEE API LOGIN ====================

import httpx
import logging
import secrets
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Store DailyShopee credentials in memory (will be loaded from database on startup)
_dailyshopee_session = {
    "logged_in": False,
    "phone": None,
    "cookie": settings.BILL_API_COOKIE,
    "csrf_token": settings.BILL_API_CSRF_TOKEN,
    "uid": None,
    "token": None
}

# Store pending login sessions for bookmarklet callback
_dailyshopee_pending_sessions = {}  # session_id -> {user_id, created_at, completed, cookie, csrf_token}


def _load_dailyshopee_credentials_from_db():
    """Load DailyShopee credentials from database on startup"""
    global _dailyshopee_session
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            # Load saved cookie from SystemConfig
            cookie_config = db.query(SystemConfig).filter(SystemConfig.key == "dailyshopee_cookie").first()
            csrf_config = db.query(SystemConfig).filter(SystemConfig.key == "dailyshopee_csrf_token").first()
            
            if cookie_config and cookie_config.value:
                _dailyshopee_session["cookie"] = cookie_config.value
                _dailyshopee_session["logged_in"] = True
                _dailyshopee_session["phone"] = "saved"
                settings.BILL_API_COOKIE = cookie_config.value
                logger.info(f"Loaded DailyShopee cookie from database (length: {len(cookie_config.value)})")
            
            if csrf_config and csrf_config.value:
                _dailyshopee_session["csrf_token"] = csrf_config.value
                settings.BILL_API_CSRF_TOKEN = csrf_config.value
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to load DailyShopee credentials from database: {e}")


def _save_dailyshopee_credentials_to_db(cookie: str, csrf_token: str = ""):
    """Save DailyShopee credentials to database for persistence"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            # Save cookie
            cookie_config = db.query(SystemConfig).filter(SystemConfig.key == "dailyshopee_cookie").first()
            if cookie_config:
                cookie_config.value = cookie
                cookie_config.updated_at = datetime.now()
            else:
                cookie_config = SystemConfig(
                    key="dailyshopee_cookie",
                    value=cookie,
                    value_type="string",
                    category="api",
                    description="DailyShopee API Cookie"
                )
                db.add(cookie_config)
            
            # Save CSRF token
            csrf_config = db.query(SystemConfig).filter(SystemConfig.key == "dailyshopee_csrf_token").first()
            if csrf_config:
                csrf_config.value = csrf_token
                csrf_config.updated_at = datetime.now()
            else:
                csrf_config = SystemConfig(
                    key="dailyshopee_csrf_token",
                    value=csrf_token,
                    value_type="string",
                    category="api",
                    description="DailyShopee API CSRF Token"
                )
                db.add(csrf_config)
            
            db.commit()
            logger.info(f"Saved DailyShopee credentials to database")
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to save DailyShopee credentials to database: {e}")
        return False


# Load credentials from database when module is imported
_load_dailyshopee_credentials_from_db()


@router.get("/dailyshopee-status")
async def get_dailyshopee_status(
    current_user: User = Depends(get_current_active_user)
):
    """Check DailyShopee login status"""
    return {
        "logged_in": _dailyshopee_session.get("logged_in", False),
        "phone": _dailyshopee_session.get("phone"),
        "has_token": bool(_dailyshopee_session.get("token") or _dailyshopee_session.get("cookie"))
    }


@router.post("/dailyshopee-login")
async def dailyshopee_login(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """
    Login to DailyShopee and get API credentials.
    """
    phone = data.get("phone", "").strip()
    password = data.get("password", "")
    account_type = data.get("account_type", "agent")  # agent or employee
    
    if not phone or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập số điện thoại và mật khẩu"
        )
    
    try:
        # DailyShopee login URL
        login_url = "https://api.dailyshopee.vn/airpay/v1/auth.UserInfoService/Login"
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://web.dailyshopee.vn',
            'Referer': 'https://web.dailyshopee.vn/login'
        }
        
        # Payload for login
        payload = {
            "phone": phone,
            "password": password,
            "user_type": 1 if account_type == "agent" else 2  # 1 = agent, 2 = employee
        }
        
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(login_url, json=payload, headers=headers)
            
            logger.info(f"DailyShopee login response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.info(f"DailyShopee login result: {json.dumps(result)[:500]}")
                    
                    # Check for successful login
                    if result.get("error") == 0 or result.get("code") == 0:
                        data_resp = result.get("data", {})
                        
                        # Extract token and uid from response
                        token = data_resp.get("token") or result.get("token")
                        uid = data_resp.get("uid") or data_resp.get("user_id") or result.get("uid")
                        
                        # Get cookies from response headers
                        cookies = response.cookies
                        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                        
                        # Build full cookie string
                        if token:
                            if "token=" not in cookie_str:
                                cookie_str = f"token={token}; {cookie_str}" if cookie_str else f"token={token}"
                        if uid:
                            if "uid=" not in cookie_str:
                                cookie_str = f"{cookie_str}; uid={uid}" if cookie_str else f"uid={uid}"
                        
                        # Get CSRF token from response headers or data
                        csrf_token = response.headers.get("x-csrf-token") or data_resp.get("csrf_token") or settings.BILL_API_CSRF_TOKEN
                        
                        # Update session
                        _dailyshopee_session["logged_in"] = True
                        _dailyshopee_session["phone"] = phone
                        _dailyshopee_session["token"] = token
                        _dailyshopee_session["uid"] = uid
                        _dailyshopee_session["cookie"] = cookie_str if cookie_str else settings.BILL_API_COOKIE
                        _dailyshopee_session["csrf_token"] = csrf_token
                        
                        # Update global settings (in memory)
                        settings.BILL_API_COOKIE = _dailyshopee_session["cookie"]
                        settings.BILL_API_CSRF_TOKEN = _dailyshopee_session["csrf_token"]
                        
                        # Save to database for persistence
                        _save_dailyshopee_credentials_to_db(_dailyshopee_session["cookie"], csrf_token)
                        
                        logger.info(f"DailyShopee login successful for {phone}")
                        
                        return {
                            "success": True,
                            "message": "Đăng nhập thành công",
                            "phone": phone,
                            "has_token": bool(token)
                        }
                    else:
                        # Login failed
                        error_msg = result.get("message") or result.get("msg") or "Đăng nhập thất bại"
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=error_msg
                        )
                        
                except json.JSONDecodeError:
                    logger.error(f"DailyShopee response not JSON: {response.text[:500]}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Lỗi đọc phản hồi từ DailyShopee"
                    )
            else:
                logger.error(f"DailyShopee login failed: {response.status_code} - {response.text[:500]}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Đăng nhập thất bại: {response.status_code}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Kết nối đến DailyShopee timeout"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DailyShopee login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi đăng nhập: {str(e)}"
        )


@router.post("/dailyshopee-save-token")
async def dailyshopee_save_token(
    data: dict,
    current_user: User = Depends(get_current_active_user)
):
    """
    Save DailyShopee token manually (after user logs in via popup window)
    """
    global _dailyshopee_session
    
    token = data.get("token", "").strip()
    uid = data.get("uid", "").strip()
    csrf_token = data.get("csrf_token", "").strip()
    
    if not token or not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token và UID là bắt buộc"
        )
    
    try:
        # Build cookie string
        cookie_str = f"token={token}; uid={uid}"
        
        # Update session
        _dailyshopee_session["logged_in"] = True
        _dailyshopee_session["phone"] = f"uid:{uid[:8]}..."
        _dailyshopee_session["token"] = token
        _dailyshopee_session["uid"] = uid
        _dailyshopee_session["cookie"] = cookie_str
        _dailyshopee_session["csrf_token"] = csrf_token if csrf_token else ""
        
        # Update global settings
        settings.BILL_API_COOKIE = cookie_str
        if csrf_token:
            settings.BILL_API_CSRF_TOKEN = csrf_token
        
        # Save to database for persistence
        _save_dailyshopee_credentials_to_db(cookie_str, csrf_token)
        
        logger.info(f"DailyShopee token saved manually by user {current_user.username}")
        
        return {
            "success": True,
            "message": "Token đã được lưu thành công (sẽ được giữ lại sau khi khởi động lại)",
            "has_token": True
        }
        
    except Exception as e:
        logger.error(f"Error saving DailyShopee token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi lưu token: {str(e)}"
        )


@router.post("/dailyshopee-save-cookie")
async def dailyshopee_save_cookie(
    data: dict,
    current_user: User = Depends(get_current_active_user)
):
    """
    Save DailyShopee cookie directly (from DevTools Request Headers)
    """
    global _dailyshopee_session
    
    cookie = data.get("cookie", "").strip()
    csrf_token = data.get("csrf_token", "").strip()
    
    if not cookie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookie là bắt buộc"
        )
    
    try:
        # Update session
        _dailyshopee_session["logged_in"] = True
        _dailyshopee_session["cookie"] = cookie
        _dailyshopee_session["csrf_token"] = csrf_token if csrf_token else ""
        _dailyshopee_session["phone"] = "manual"
        
        # Extract token and uid from cookie if present
        import re
        token_match = re.search(r'token=([^;]+)', cookie)
        uid_match = re.search(r'uid=([^;]+)', cookie)
        
        if token_match:
            _dailyshopee_session["token"] = token_match.group(1)
        if uid_match:
            _dailyshopee_session["uid"] = uid_match.group(1)
        
        # Update global settings
        settings.BILL_API_COOKIE = cookie
        if csrf_token:
            settings.BILL_API_CSRF_TOKEN = csrf_token
        
        # Save to database for persistence
        _save_dailyshopee_credentials_to_db(cookie, csrf_token)
        
        logger.info(f"DailyShopee cookie saved manually by user {current_user.username}")
        logger.info(f"  Cookie length: {len(cookie)}, CSRF: {'Yes' if csrf_token else 'No'}")
        
        return {
            "success": True,
            "message": "Cookie đã được lưu thành công (sẽ được giữ lại sau khi khởi động lại)",
            "cookie_length": len(cookie)
        }
        
    except Exception as e:
        logger.error(f"Error saving DailyShopee cookie: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi lưu cookie: {str(e)}"
        )


@router.get("/dailyshopee-test")
async def dailyshopee_test_connection(
    current_user: User = Depends(get_current_active_user)
):
    """
    Test DailyShopee API connection by making a simple request
    """
    cookie = _dailyshopee_session.get("cookie", settings.BILL_API_COOKIE)
    csrf_token = _dailyshopee_session.get("csrf_token", settings.BILL_API_CSRF_TOKEN)
    
    if not cookie:
        return {
            "success": False,
            "message": "Chưa có Cookie. Vui lòng đăng nhập DailyShopee."
        }
    
    try:
        # Test with a simple bill lookup
        api_url = f"{settings.BILL_API_BASE_URL}{settings.BILL_API_PATH}"
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Cookie': cookie,
            'Origin': 'https://web.dailyshopee.vn',
            'Referer': 'https://web.dailyshopee.vn/'
        }
        
        if csrf_token:
            headers['X-Csrf-Token'] = csrf_token
        
        # Test request with a dummy customer code
        test_payload = {
            "customer_code": "TEST123",
            "provider_sku": "00906815"  # EVN South
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(api_url, json=test_payload, headers=headers)
            
            # If we get a response (even error), the connection works
            if response.status_code in [200, 400, 404]:
                return {
                    "success": True,
                    "message": f"Kết nối thành công! (Status: {response.status_code})"
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": "Cookie hết hạn. Vui lòng đăng nhập lại."
                }
            else:
                return {
                    "success": False,
                    "message": f"Lỗi kết nối: HTTP {response.status_code}"
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "Timeout khi kết nối đến DailyShopee"
        }
    except Exception as e:
        logger.error(f"DailyShopee test error: {e}")
        return {
            "success": False,
            "message": f"Lỗi: {str(e)}"
        }


@router.post("/dailyshopee-start-session")
async def dailyshopee_start_session(
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new session for bookmarklet-based cookie capture.
    Returns a session ID that the bookmarklet will use to send cookies back.
    """
    global _dailyshopee_pending_sessions
    
    # Clean up old sessions (older than 10 minutes)
    now = datetime.now()
    expired = [sid for sid, data in _dailyshopee_pending_sessions.items() 
               if now - data["created_at"] > timedelta(minutes=10)]
    for sid in expired:
        del _dailyshopee_pending_sessions[sid]
    
    # Create new session
    session_id = secrets.token_urlsafe(32)
    _dailyshopee_pending_sessions[session_id] = {
        "user_id": current_user.id,
        "username": current_user.username,
        "created_at": now,
        "completed": False,
        "cookie": None,
        "csrf_token": None
    }
    
    logger.info(f"Created DailyShopee session {session_id[:8]}... for user {current_user.username}")
    
    return {
        "success": True,
        "session_id": session_id
    }


@router.get("/dailyshopee-check-session/{session_id}")
async def dailyshopee_check_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Check if the bookmarklet has sent cookies for this session.
    Frontend polls this endpoint after user clicks bookmarklet.
    """
    session = _dailyshopee_pending_sessions.get(session_id)
    
    if not session:
        return {"completed": False, "error": "Session not found or expired"}
    
    if session["user_id"] != current_user.id:
        return {"completed": False, "error": "Unauthorized"}
    
    if session["completed"]:
        # Update global session
        global _dailyshopee_session
        _dailyshopee_session["logged_in"] = True
        _dailyshopee_session["cookie"] = session["cookie"]
        _dailyshopee_session["csrf_token"] = session.get("csrf_token", "")
        _dailyshopee_session["token"] = session.get("token", "")
        _dailyshopee_session["uid"] = session.get("uid", "")
        _dailyshopee_session["phone"] = f"bookmarklet:{session_id[:8]}..."
        
        # Update settings for API calls
        settings.BILL_API_COOKIE = session["cookie"]
        if session.get("csrf_token"):
            settings.BILL_API_CSRF_TOKEN = session["csrf_token"]
        
        logger.info(f"DailyShopee session {session_id[:8]}... completed - Cookie: {len(session['cookie'])} chars")
        
        # Clean up session
        del _dailyshopee_pending_sessions[session_id]
        
        return {
            "completed": True,
            "success": True,
            "message": "Cookie đã được cập nhật thành công!"
        }
    
    return {"completed": False}


from fastapi import Response
from fastapi.responses import HTMLResponse

@router.post("/dailyshopee-callback")
async def dailyshopee_callback(
    data: dict,
    response: Response
):
    """
    Receive cookies from bookmarklet (CORS-enabled for cross-origin requests).
    This endpoint doesn't require auth - it uses session_id for verification.
    
    Expects:
    - session_id: The session ID
    - cookie: Full document.cookie string
    - token: Token from localStorage (optional)
    - uid: UID from localStorage (optional)  
    - csrf_token: CSRF token from localStorage (optional)
    """
    # Add CORS headers
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    
    session_id = data.get("session_id", "").strip()
    cookie = data.get("cookie", "").strip()
    token = data.get("token", "").strip()
    uid = data.get("uid", "").strip()
    csrf_token = data.get("csrf_token", "").strip()
    
    if not session_id:
        return {"success": False, "error": "Missing session_id"}
    
    if not cookie and not token:
        return {"success": False, "error": "Missing cookie or token"}
    
    session = _dailyshopee_pending_sessions.get(session_id)
    
    if not session:
        return {"success": False, "error": "Session not found or expired"}
    
    # Build the best possible cookie string
    final_cookie = cookie
    if token and f"token={token}" not in cookie:
        final_cookie += f"; token={token}"
    if uid and f"uid={uid}" not in cookie:
        final_cookie += f"; uid={uid}"
    
    # Clean up the cookie string
    final_cookie = final_cookie.strip("; ")
    
    # Mark session as completed with the cookie
    session["completed"] = True
    session["cookie"] = final_cookie
    session["csrf_token"] = csrf_token
    session["token"] = token
    session["uid"] = uid
    
    logger.info(f"Received cookie from bookmarklet for session {session_id[:8]}...")
    logger.info(f"  Cookie length: {len(final_cookie)}, Token: {'Yes' if token else 'No'}, UID: {'Yes' if uid else 'No'}, CSRF: {'Yes' if csrf_token else 'No'}")
    
    return {
        "success": True,
        "message": "Cookie received! You can close this tab now.",
        "has_token": bool(token),
        "has_uid": bool(uid),
        "has_csrf": bool(csrf_token)
    }


@router.options("/dailyshopee-callback")
async def dailyshopee_callback_options(response: Response):
    """Handle CORS preflight request"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return {"status": "ok"}


def get_dailyshopee_credentials():
    """Get current DailyShopee API credentials"""
    return {
        "cookie": _dailyshopee_session.get("cookie", settings.BILL_API_COOKIE),
        "csrf_token": _dailyshopee_session.get("csrf_token", settings.BILL_API_CSRF_TOKEN)
    }


# ==================== PROXY POOL MANAGEMENT ====================

@router.get("/proxy/list")
async def get_proxy_list(
    current_user: User = Depends(get_current_active_admin)
):
    """Lấy danh sách và trạng thái proxy pool"""
    try:
        from services.proxy_service import proxy_pool
        stats = proxy_pool.get_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@router.post("/proxy/add")
async def add_proxy(
    proxy_url: str,
    current_user: User = Depends(get_current_active_admin)
):
    """Thêm proxy mới vào pool"""
    try:
        from services.proxy_service import proxy_pool, parse_proxy_string
        
        # Parse custom format (IP:PORT:USER:PASS) to standard format
        parsed_url = parse_proxy_string(proxy_url)
        if not parsed_url:
            raise HTTPException(400, "Định dạng proxy không hợp lệ. Hỗ trợ: http://user:pass@ip:port hoặc IP:PORT:USER:PASS")
        
        result = proxy_pool.add_proxy(parsed_url)
        if result:
            return {
                "success": True,
                "message": "Đã thêm proxy thành công"
            }
        else:
            return {
                "success": False,
                "message": "Proxy đã tồn tại trong pool"
            }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@router.post("/proxy/add-batch")
async def add_proxies_batch(
    proxies: List[str],
    current_user: User = Depends(get_current_active_admin)
):
    """Thêm nhiều proxy cùng lúc"""
    try:
        from services.proxy_service import proxy_pool, parse_proxy_string
        
        added = 0
        skipped = 0
        failed = 0
        for proxy_str in proxies:
            proxy_str = proxy_str.strip()
            if not proxy_str:
                continue
            
            # Parse custom format to standard format
            proxy_url = parse_proxy_string(proxy_str)
            if proxy_url:
                if proxy_pool.add_proxy(proxy_url):
                    added += 1
                else:
                    skipped += 1
            else:
                failed += 1
        
        message = f"Đã thêm {added} proxy"
        if skipped > 0:
            message += f", bỏ qua {skipped} proxy trùng"
        if failed > 0:
            message += f", {failed} proxy lỗi format"
        
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@router.delete("/proxy/remove")
async def remove_proxy(
    proxy_url: str,
    current_user: User = Depends(get_current_active_admin)
):
    """Xóa proxy khỏi pool"""
    try:
        from services.proxy_service import proxy_pool
        
        result = proxy_pool.remove_proxy(proxy_url)
        if result:
            return {
                "success": True,
                "message": "Đã xóa proxy"
            }
        else:
            return {
                "success": False,
                "message": "Không tìm thấy proxy"
            }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@router.post("/proxy/clear")
async def clear_all_proxies(
    current_user: User = Depends(get_current_active_admin)
):
    """Xóa tất cả proxy"""
    try:
        from services.proxy_service import proxy_pool
        proxy_pool.clear_all()
        return {
            "success": True,
            "message": "Đã xóa tất cả proxy"
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@router.post("/proxy/enable")
async def toggle_proxy(
    enabled: bool = True,
    current_user: User = Depends(get_current_active_admin)
):
    """Bật/tắt sử dụng proxy"""
    try:
        from services.proxy_service import proxy_pool
        # Update in proxy_pool and save to database
        proxy_pool.set_enabled(enabled)
        
        logger.info(f"Proxy enabled state changed to: {enabled}")
        
        return {
            "success": True,
            "message": f"Proxy đã {'bật' if enabled else 'tắt'}",
            "enabled": enabled
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@router.get("/proxy/test")
async def test_proxy(
    proxy_url: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin)
):
    """Test proxy connection"""
    try:
        import httpx
        from services.proxy_service import proxy_pool, get_proxy_for_test, parse_proxy_string
        
        # Use provided proxy or get first proxy from pool (for testing)
        test_proxy = proxy_url or get_proxy_for_test()
        
        if not test_proxy:
            return {
                "success": False,
                "message": "Không có proxy để test. Vui lòng thêm proxy trước."
            }
        
        # Parse custom format if needed
        test_proxy = parse_proxy_string(test_proxy)
        if not test_proxy:
            return {
                "success": False,
                "message": "Định dạng proxy không hợp lệ"
            }
        
        # Test with httpbin.org to get public IP (use 'proxy' param for newer httpx)
        async with httpx.AsyncClient(timeout=10.0, proxy=test_proxy) as client:
            response = await client.get("https://httpbin.org/ip")
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": "Proxy hoạt động",
                    "proxy": test_proxy[:30] + "...",
                    "public_ip": data.get("origin", "unknown")
                }
            else:
                return {
                    "success": False,
                    "message": f"Proxy lỗi: HTTP {response.status_code}"
                }
    except Exception as e:
        return {
            "success": False,
            "message": f"Lỗi kết nối proxy: {str(e)}"
        }


@router.get("/proxy/test-all-stream")
async def test_all_proxies_stream(
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db)
):
    """Test tất cả proxy trong pool với streaming results"""
    import httpx
    import asyncio
    from fastapi.responses import StreamingResponse
    from services.proxy_service import proxy_pool
    from security import verify_token
    
    # Verify token manually since EventSource doesn't support headers
    try:
        payload = verify_token(token)
        if not payload:
            return {"success": False, "message": "Token không hợp lệ"}
        user = db.query(User).filter(User.id == payload.get("sub")).first()
        if not user or user.role != UserRole.ADMIN:
            return {"success": False, "message": "Không có quyền truy cập"}
    except Exception:
        return {"success": False, "message": "Token không hợp lệ"}
    
    async def generate_results():
        all_proxies = proxy_pool.list_proxies()
        
        if not all_proxies:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Không có proxy nào để test'})}\n\n"
            return
        
        # Send initial info
        yield f"data: {json.dumps({'type': 'start', 'total': len(all_proxies)})}\n\n"
        
        success_count = 0
        fail_count = 0
        
        for i, proxy_url in enumerate(all_proxies):
            # Test the proxy
            result = {
                "index": i + 1,
                "proxy": proxy_url[:40] + "..." if len(proxy_url) > 40 else proxy_url,
                "full_proxy": proxy_url,
                "success": False,
                "public_ip": None,
                "message": ""
            }
            
            try:
                async with httpx.AsyncClient(timeout=10.0, proxy=proxy_url) as client:
                    response = await client.get("https://httpbin.org/ip")
                    if response.status_code == 200:
                        data = response.json()
                        result["success"] = True
                        result["public_ip"] = data.get("origin", "unknown")
                        result["message"] = "OK"
                        success_count += 1
                    else:
                        result["message"] = f"HTTP {response.status_code}"
                        fail_count += 1
                        # Remove failed proxy
                        proxy_pool.remove_proxy(proxy_url)
            except Exception as e:
                result["message"] = str(e)[:50]
                fail_count += 1
                # Remove failed proxy
                proxy_pool.remove_proxy(proxy_url)
            
            # Send result
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            
            # Delay before next test (except last one)
            if i < len(all_proxies) - 1:
                await asyncio.sleep(5)
        
        # Send summary
        yield f"data: {json.dumps({'type': 'done', 'success_count': success_count, 'fail_count': fail_count, 'remaining': len(proxy_pool.list_proxies())})}\n\n"
    
    return StreamingResponse(
        generate_results(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/proxy/test-all")
async def test_all_proxies(
    current_user: User = Depends(get_current_active_admin)
):
    """Test tất cả proxy trong pool (non-streaming version)"""
    try:
        import httpx
        import asyncio
        from services.proxy_service import proxy_pool
        
        all_proxies = proxy_pool.list_proxies()
        
        if not all_proxies:
            return {
                "success": False,
                "message": "Không có proxy nào để test",
                "results": []
            }
        
        results = []
        
        async def test_single_proxy(proxy_url: str):
            """Test a single proxy and return result"""
            try:
                async with httpx.AsyncClient(timeout=10.0, proxy=proxy_url) as client:
                    response = await client.get("https://httpbin.org/ip")
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "proxy": proxy_url[:40] + "..." if len(proxy_url) > 40 else proxy_url,
                            "full_proxy": proxy_url,
                            "success": True,
                            "public_ip": data.get("origin", "unknown"),
                            "message": "OK"
                        }
                    else:
                        return {
                            "proxy": proxy_url[:40] + "..." if len(proxy_url) > 40 else proxy_url,
                            "full_proxy": proxy_url,
                            "success": False,
                            "public_ip": None,
                            "message": f"HTTP {response.status_code}"
                        }
            except Exception as e:
                return {
                    "proxy": proxy_url[:40] + "..." if len(proxy_url) > 40 else proxy_url,
                    "full_proxy": proxy_url,
                    "success": False,
                    "public_ip": None,
                    "message": str(e)[:50]
                }
        
        # Test proxies sequentially with 5 second delay between each
        for i, proxy in enumerate(all_proxies):
            result = await test_single_proxy(proxy)
            results.append(result)
            
            # Auto-remove failed proxies
            if not result["success"]:
                proxy_pool.remove_proxy(proxy)
            
            # Add 5 second delay between tests (except after the last one)
            if i < len(all_proxies) - 1:
                await asyncio.sleep(5)
        
        # Count success/fail
        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count
        
        return {
            "success": True,
            "message": f"Đã test {len(results)} proxy: {success_count} thành công, {fail_count} thất bại. Còn lại {len(proxy_pool.list_proxies())} proxy hoạt động.",
            "total": len(results),
            "success_count": success_count,
            "fail_count": fail_count,
            "remaining": len(proxy_pool.list_proxies()),
            "results": results
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Lỗi: {str(e)}",
            "results": []
        }


# ==================== SYSTEM BANK ACCOUNTS ====================

# Store bank accounts in JSON file
BANK_ACCOUNTS_FILE = Path("data/system_bank_accounts.json")

def load_bank_accounts_from_file():
    """Load bank accounts from JSON file"""
    try:
        if BANK_ACCOUNTS_FILE.exists():
            with open(BANK_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading bank accounts: {e}")
    return []

def save_bank_accounts_to_file(accounts):
    """Save bank accounts to JSON file"""
    try:
        BANK_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BANK_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving bank accounts: {e}")
        return False

@router.get("/bank-accounts")
async def get_system_bank_accounts(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of system bank accounts for deposit
    """
    accounts = load_bank_accounts_from_file()
    return {
        "success": True,
        "items": accounts,
        "total": len(accounts)
    }

@router.post("/bank-accounts")
async def save_system_bank_accounts(
    accounts: List[Dict[str, Any]],
    current_user: User = Depends(get_current_active_user)
):
    """
    Save system bank accounts (admin/manager only)
    """
    # Check if user is admin or manager
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin hoặc Manager mới có quyền thực hiện"
        )
    
    if save_bank_accounts_to_file(accounts):
        return {
            "success": True,
            "message": f"Đã lưu {len(accounts)} tài khoản ngân hàng",
            "items": accounts
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lưu tài khoản ngân hàng"
        )