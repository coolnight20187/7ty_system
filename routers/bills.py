from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, or_, and_
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import logging
from decimal import Decimal
from pathlib import Path
import pandas as pd
import re

from config import settings
from database import get_db, paginate_query
from dependencies import (
    get_current_user, require_role, manager_or_admin, 
    admin_only, pagination_params, bill_filter_params,
    get_current_active_agent, get_current_agent
)
from models import (
    User, UserRole, Agent, AgentStatus,
    Bill, BillStatus, Customer, Transaction,
    TransactionType, TransactionStatus, CommissionLog,
    ActivityLog, UploadedFile
)
from schemas import (
    BillBase, BillCreate, BillUpdate, BillResponse,
    BillImportRequest, BillImportResponse, PaginatedResponse,
    SuccessResponse, ErrorResponse, DateRange, ReportResponse,
    TransactionCreate, TransactionResponse
)
from utils import (
    FormatUtils, ValidationUtils, FileUtils, ExportUtils,
    ImportUtils, EmailUtils, CacheUtils, CalculationUtils
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Bills"])

# Helper functions
def generate_bill_code(db: Session) -> str:
    """Generate unique bill code in format BILLxxxxxx"""
    # Get the latest bill to determine next number
    latest_bill = db.query(Bill).order_by(desc(Bill.id)).first()
    
    if latest_bill and latest_bill.bill_code:
        # Try to extract number from existing code
        code = latest_bill.bill_code
        if code.startswith('BILL'):
            try:
                # Extract number part (could be BILLxxxxxx or BILLYYYYMMDDxxxxxx)
                num_part = ''.join(filter(str.isdigit, code))
                if len(num_part) >= 6:
                    # Use last 6 digits for new format
                    next_num = int(num_part[-6:]) + 1
                else:
                    next_num = int(num_part) + 1 if num_part else 1
            except:
                next_num = latest_bill.id + 1
        else:
            next_num = latest_bill.id + 1
    else:
        next_num = 1
    
    bill_code = f"BILL{next_num:06d}"
    
    # Ensure uniqueness
    while db.query(Bill).filter(Bill.bill_code == bill_code).first():
        next_num += 1
        bill_code = f"BILL{next_num:06d}"
    
    return bill_code

def get_bill_query(db: Session, filters: Dict[str, Any] = None):
    """Build query for bills with filters"""
    query = db.query(Bill)
    
    if not filters:
        return query
    
    # Apply filters
    if filters.get("status"):
        # Convert status string to BillStatus enum (case-insensitive)
        status_str = filters["status"].upper()
        try:
            status_enum = BillStatus(status_str.lower())
            query = query.filter(Bill.status == status_enum)
        except ValueError:
            # If invalid status, try to match directly
            query = query.filter(Bill.status == filters["status"])
    
    if filters.get("period_from"):
        query = query.filter(Bill.period >= filters["period_from"])
    
    if filters.get("period_to"):
        query = query.filter(Bill.period <= filters["period_to"])
    
    # Exact period match
    if filters.get("period"):
        query = query.filter(Bill.period == filters["period"])
    
    if filters.get("agent_id"):
        query = query.filter(Bill.agent_id == filters["agent_id"])
    
    if filters.get("customer_code"):
        query = query.filter(Bill.customer_code.ilike(f"%{filters['customer_code']}%"))
    
    # Quick search - search across multiple fields
    if filters.get("search"):
        search_term = f"%{filters['search']}%"
        query = query.filter(
            or_(
                Bill.customer_code.ilike(search_term),
                Bill.customer_name.ilike(search_term),
                Bill.bill_code.ilike(search_term),
                Bill.customer_address.ilike(search_term)
            )
        )
    
    # Provider filter
    if filters.get("provider"):
        query = query.filter(Bill.provider == filters["provider"])
    
    if filters.get("amount_from"):
        query = query.filter(Bill.total_amount >= filters["amount_from"])
    
    if filters.get("amount_to"):
        query = query.filter(Bill.total_amount <= filters["amount_to"])
    
    return query

def calculate_bill_stats(db: Session, filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """Calculate bill statistics"""
    query = get_bill_query(db, filters)
    
    # Total bills
    total_bills = query.count()
    
    # Total amount
    total_amount = db.query(func.sum(Bill.total_amount)).filter(
        Bill.id.in_([b.id for b in query.all()])
    ).scalar() or Decimal('0')
    
    # By status
    status_query = query.group_by(Bill.status)
    status_counts = {status.value: 0 for status in BillStatus}
    for status, count in status_query.with_entities(Bill.status, func.count(Bill.id)).all():
        if status:
            status_counts[status.value] = count
    
    # Overdue bills
    overdue_bills = db.query(func.count(Bill.id)).filter(
        Bill.status.in_([BillStatus.IN_STOCK, BillStatus.PENDING]),
        Bill.due_date < date.today()
    ).scalar() or 0
    
    # Today's sales
    today_sales = db.query(func.sum(Bill.total_amount)).filter(
        Bill.status.in_([BillStatus.SOLD, BillStatus.PAID]),
        func.date(Bill.payment_date) == date.today()
    ).scalar() or Decimal('0')
    
    return {
        "total_bills": total_bills,
        "total_amount": float(total_amount),
        "by_status": status_counts,
        "overdue_bills": overdue_bills,
        "today_sales": float(today_sales)
    }

def create_bill_activity_log(
    db: Session, 
    user_id: int, 
    action: str, 
    bill_id: int, 
    details: str = None
):
    """Create activity log for bill actions"""
    activity = ActivityLog(
        user_id=user_id,
        activity_type="update",
        action=action,
        resource_type="bill",
        resource_id=bill_id,
        details=details
    )
    db.add(activity)
    db.commit()

def validate_bill_data(bill_data: Dict[str, Any]) -> List[str]:
    """Validate bill data"""
    errors = []
    
    # Validate period format (YYYY-MM)
    if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', bill_data.get('period', '')):
        errors.append("Invalid period format. Must be YYYY-MM")
    
    # Validate amounts
    try:
        total_amount = Decimal(str(bill_data.get('total_amount', 0)))
        if total_amount <= 0:
            errors.append("Total amount must be greater than 0")
    except:
        errors.append("Invalid total amount")
    
    # Validate customer information
    if not bill_data.get('customer_code'):
        errors.append("Customer code is required")
    
    if not bill_data.get('customer_name'):
        errors.append("Customer name is required")
    
    return errors

def process_bill_payment(
    db: Session,
    bill: Bill,
    payment_method: str,
    transaction_ref: str,
    current_user: User
) -> Transaction:
    """Process bill payment"""
    # Generate transaction code
    transaction_code = f"PAY{datetime.now().strftime('%Y%m%d%H%M%S')}{bill.id:06d}"
    
    # Create transaction
    transaction = Transaction(
        transaction_code=transaction_code,
        user_id=current_user.id,
        agent_id=bill.agent_id,
        bill_id=bill.id,
        transaction_type=TransactionType.BILL_PAYMENT,
        amount=bill.total_amount,
        total_amount=bill.total_amount,
        description=f"Payment for bill {bill.bill_code}",
        status=TransactionStatus.COMPLETED,
        payment_method=payment_method,
        completed_at=datetime.utcnow(),
        notes=f"Payment reference: {transaction_ref}"
    )
    
    # Update bill status
    bill.status = BillStatus.PAID
    bill.payment_date = datetime.utcnow()
    bill.payment_method = payment_method
    bill.transaction_ref = transaction_ref
    
    # Update agent statistics if bill has agent
    if bill.agent_id:
        agent = db.query(Agent).filter(Agent.id == bill.agent_id).first()
        if agent:
            agent.total_sales += bill.total_amount
            agent.total_successful_bills += 1
            agent.total_bills += 1
            
            # Recalculate success rate
            if agent.total_bills > 0:
                agent.success_rate = (agent.total_successful_bills / agent.total_bills) * 100
    
    db.add(transaction)
    db.commit()
    
    return transaction

def assign_bill_to_agent(
    db: Session,
    bill: Bill,
    agent_id: int,
    current_user: User
) -> bool:
    """Assign bill to agent"""
    # Check if agent exists and is active
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        return False
    
    if agent.status != AgentStatus.ACTIVE:
        return False
    
    # Check if agent has sufficient balance
    if agent.available_balance < bill.total_amount:
        return False
    
    # Freeze agent balance
    agent.frozen_balance += bill.total_amount
    agent.updated_at = datetime.utcnow()
    
    # Update bill
    bill.agent_id = agent_id
    bill.status = BillStatus.SOLD
    
    # Calculate commission
    commission_amount = CalculationUtils.calculate_commission(
        bill.total_amount, agent.commission_rate
    )
    bill.agent_commission = commission_amount
    
    # Create commission log
    commission_log = CommissionLog(
        agent_id=agent_id,
        bill_id=bill.id,
        bill_amount=bill.total_amount,
        commission_rate=agent.commission_rate,
        commission_amount=commission_amount,
        calculated_at=datetime.utcnow()
    )
    
    db.add(commission_log)
    db.commit()
    
    # Create activity log
    create_bill_activity_log(
        db, current_user.id,
        "Bill assigned to agent",
        bill.id,
        f"Bill assigned to agent {agent.agent_code}. Commission: {FormatUtils.format_currency(commission_amount)}"
    )
    
    return True

# Routes
@router.get("")
async def get_bills(
    pagination: Dict = Depends(pagination_params),
    filters: Dict = Depends(bill_filter_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of bills with pagination and filtering
    """
    try:
        # If user is agent, only show their bills
        if current_user.role == UserRole.AGENT:
            agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
            if agent:
                filters["agent_id"] = agent.id
            else:
                # Agent profile not found, return empty
                return {
                    "page": 1,
                    "limit": 10,
                    "total": 0,
                    "pages": 0,
                    "data": []
                }
        
        # Build query
        query = get_bill_query(db, filters)
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        sort_by = pagination.get("sort_by", "created_at") or "created_at"
        sort_order = pagination.get("sort_order", "desc") or "desc"
        
        sort_column = getattr(Bill, sort_by, None)
        if sort_column is None:
            sort_column = Bill.created_at
        
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        bills = query.options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer),
            joinedload(Bill.creator)
        ).offset((page - 1) * limit).limit(limit).all()
        
        # Convert to dict for serialization
        bills_data = []
        for bill in bills:
            bill_dict = {
                "id": bill.id,
                "bill_code": bill.bill_code,
                "transaction_code": bill.transaction_ref or bill.bill_code,  # Mã giao dịch
                "customer_code": bill.customer_code,
                "customer_name": bill.customer_name,
                "customer_address": bill.customer_address,
                "period": bill.period,
                "total_amount": float(bill.total_amount) if bill.total_amount else 0,
                "status": bill.status.value if bill.status else "pending",
                "due_date": bill.due_date.isoformat() if bill.due_date else None,
                "payment_date": bill.payment_date.isoformat() if bill.payment_date else None,
                "agent_id": bill.agent_id,
                "agent_code": bill.agent.agent_code if bill.agent else None,  # Mã đại lý
                "customer_id": bill.customer_id,
                "created_at": bill.created_at.isoformat() if bill.created_at else None,
                "updated_at": bill.updated_at.isoformat() if bill.updated_at else None,
                "notes": bill.notes,
                "created_by": bill.creator.full_name if bill.creator else None,
                "provider": bill.provider if hasattr(bill, 'provider') else None,
            }
            
            # Add agent info if available
            if bill.agent:
                bill_dict["agent"] = {
                    "id": bill.agent.id,
                    "agent_code": bill.agent.agent_code,
                    "full_name": bill.agent.user.full_name if bill.agent.user else None
                }
            
            # Add customer info if available
            if bill.customer:
                bill_dict["customer"] = {
                    "id": bill.customer.id,
                    "customer_code": bill.customer.customer_code,
                    "full_name": bill.customer.full_name
                }
            
            bills_data.append(bill_dict)
        
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
            "data": bills_data
        }
        
    except Exception as e:
        logger.error(f"Get bills error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách hóa đơn"
        )

@router.get("/stats", response_model=Dict[str, Any])
@manager_or_admin()
async def get_bills_stats(
    filters: Dict = Depends(bill_filter_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bills statistics overview
    """
    try:
        stats = calculate_bill_stats(db, filters)
        
        # Additional statistics
        # Monthly trend
        monthly_stats = db.query(
            func.date_trunc('month', Bill.created_at).label('month'),
            func.count(Bill.id).label('count'),
            func.sum(Bill.total_amount).label('amount')
        ).filter(
            Bill.created_at >= datetime.utcnow() - timedelta(days=365)
        ).group_by(
            func.date_trunc('month', Bill.created_at)
        ).order_by(
            func.date_trunc('month', Bill.created_at).desc()
        ).limit(6).all()
        
        # Top agents by bill count
        top_agents = db.query(
            Agent.agent_code,
            User.full_name,
            func.count(Bill.id).label('bill_count'),
            func.sum(Bill.total_amount).label('total_amount')
        ).join(
            User, Agent.user_id == User.id
        ).join(
            Bill, Agent.id == Bill.agent_id
        ).filter(
            Bill.created_at >= datetime.utcnow() - timedelta(days=30)
        ).group_by(
            Agent.agent_code, User.full_name
        ).order_by(
            desc(func.count(Bill.id))
        ).limit(5).all()
        
        return {
            "success": True,
            "stats": stats,
            "monthly_trend": [
                {
                    "month": month.strftime("%Y-%m"),
                    "count": count,
                    "amount": float(amount) if amount else 0
                }
                for month, count, amount in monthly_stats
            ],
            "top_agents": [
                {
                    "agent_code": agent_code,
                    "full_name": full_name,
                    "bill_count": bill_count,
                    "total_amount": float(total_amount) if total_amount else 0
                }
                for agent_code, full_name, bill_count, total_amount in top_agents
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Get bills stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy thống kê hóa đơn"
        )


# ==================== BULK LOOKUP ENDPOINTS ====================
# Note: These must be placed BEFORE /{bill_id} route to avoid path matching issues

import httpx

# Provider SKU mapping
PROVIDER_SKU_MAP = {
    'evn_south': '00906815',    # Điện lực miền Nam
    'evn_north': '00906819',    # Điện lực miền Bắc  
    'evn_hcm': '00906818',      # EVNHCMC
    'evn_hanoi': '00906820'     # EVN Hà Nội
}

async def _local_lookup(customer_code: str, provider: str, db: Session):
    """
    Fallback lookup when external API is not available.
    First checks database, then simulates data for demo.
    """
    # Check if bill exists in database
    existing_bill = db.query(Bill).filter(
        or_(
            Bill.customer_code == customer_code,
            Bill.evn_customer_code == customer_code
        )
    ).order_by(desc(Bill.created_at)).first()
    
    if existing_bill:
        return {
            "success": True,
            "source": "database",
            "customer_code": customer_code,
            "customer_name": existing_bill.customer_name,
            "address": existing_bill.customer_address or "",
            "total_amount": float(existing_bill.total_amount) if existing_bill.total_amount else 0,
            "period": existing_bill.period,
            "status": existing_bill.status,
            "bill_id": existing_bill.id
        }
    
    # Check if customer exists in customer database
    customer = db.query(Customer).filter(
        or_(
            Customer.customer_code == customer_code,
            Customer.evn_customer_code == customer_code
        )
    ).first()
    
    if customer:
        return {
            "success": True,
            "source": "customer",
            "customer_code": customer_code,
            "customer_name": customer.full_name or "-",
            "address": customer.address or "",
            "total_amount": 0,
            "period": None,
            "status": "not_found",
            "customer_id": customer.id
        }
    
    # Simulate lookup result for demo purposes
    import random
    import hashlib
    
    # Generate consistent "random" data based on customer code
    seed = int(hashlib.md5(customer_code.encode()).hexdigest()[:8], 16)
    random.seed(seed)
    
    # Check if code looks valid
    if len(customer_code) < 8:
        return {
            "success": False,
            "source": "simulation",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": "Mã khách hàng không hợp lệ",
            "total_amount": 0,
            "status": "invalid"
        }
    
    # Simulate found data - 80% có hóa đơn
    has_bill = random.random() > 0.2
    
    if has_bill:
        amount = random.randint(50000, 500000) * 10  # 500k - 5M
        return {
            "success": True,
            "source": "simulation",
            "customer_code": customer_code,
            "customer_name": f"Khách hàng {customer_code[-4:]}",
            "address": f"Số {random.randint(1, 200)}, Đường {random.randint(1, 50)}, Phường {random.randint(1, 20)}",
            "total_amount": amount,
            "period": datetime.now().strftime("%m/%Y"),
            "status": "pending",
            "provider": provider
        }
    else:
        return {
            "success": True,
            "source": "simulation",
            "customer_code": customer_code,
            "customer_name": f"Khách hàng {customer_code[-4:]}",
            "address": "Không nợ cước",
            "total_amount": 0,
            "period": datetime.now().strftime("%m/%Y"),
            "status": "paid",
            "provider": provider
        }


@router.get("/history")
@manager_or_admin()
async def get_bill_history(
    from_date: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bill activity history
    """
    try:
        query = db.query(ActivityLog).filter(
            ActivityLog.resource_type == "bill"
        )
        
        # Filter by date range
        if from_date:
            try:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                query = query.filter(ActivityLog.created_at >= from_dt)
            except:
                pass
        
        if to_date:
            try:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(ActivityLog.created_at < to_dt)
            except:
                pass
        
        # Get total count
        total = query.count()
        
        # Get items with pagination
        items = query.order_by(desc(ActivityLog.created_at)).offset(skip).limit(limit).all()
        
        # Format response
        result = []
        for item in items:
            # Get bill info if available
            bill_info = {}
            if item.resource_id:
                bill = db.query(Bill).filter(Bill.id == item.resource_id).first()
                if bill:
                    bill_info = {
                        "bill_code": bill.bill_code,
                        "customer_code": bill.customer_code
                    }
            
            # Get user info
            user_name = "System"
            if item.user_id:
                user = db.query(User).filter(User.id == item.user_id).first()
                if user:
                    user_name = user.full_name or user.username
            
            result.append({
                "id": item.id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "action": item.action,
                "details": item.details,
                "bill_code": bill_info.get("bill_code", "N/A"),
                "customer_code": bill_info.get("customer_code", "N/A"),
                "user_name": user_name,
                "ip_address": item.ip_address if hasattr(item, 'ip_address') else "N/A"
            })
        
        return {
            "items": result,
            "total": total,
            "page": (skip // limit) + 1,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Get bill history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể lấy lịch sử hóa đơn: {str(e)}"
        )


@router.post("/lookup")
@manager_or_admin()
async def lookup_bill(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lookup electricity bill information by customer code using selected gateway.
    Supports: dailyshopee (Cổng 1) and fptshop (Cổng 2)
    Each gateway has different supported providers.
    """
    try:
        customer_code = data.get('customer_code', '').strip().upper()
        provider = data.get('provider', 'evn_south')
        gateway = data.get('gateway', 'dailyshopee')  # Default to dailyshopee
        
        if not customer_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng nhập mã khách hàng"
            )
        
        # DailyShopee hỗ trợ 4 nhà cung cấp
        DAILYSHOPEE_SUPPORTED = ['evn_south', 'evn_hcm', 'evn_hanoi', 'evn_central']
        if gateway == 'dailyshopee' and provider not in DAILYSHOPEE_SUPPORTED:
            return {
                "success": False,
                "source": "dailyshopee",
                "customer_code": customer_code,
                "customer_name": f"(Mã {customer_code})",
                "address": f"Cổng 1 (DailyShopee) không hỗ trợ nhà cung cấp này. Vui lòng chuyển sang Cổng 2 (FPT Shop).",
                "total_amount": 0,
                "status": "not_supported",
                "provider": provider
            }
        
        # Route to appropriate gateway
        if gateway == 'fptshop':
            return await _lookup_via_fptshop(customer_code, provider, db)
        else:
            return await _lookup_via_dailyshopee(customer_code, provider, db)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lookup bill error: {e}")
        return {
            "success": False,
            "source": "error",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": f"Lỗi: {str(e)}",
            "total_amount": 0,
            "status": "error",
            "provider": provider
        }


async def _lookup_via_fptshop(customer_code: str, provider: str, db: Session):
    """
    Lookup electricity bill via FPT Shop API (Cổng 2)
    API endpoint: https://papi.fptshop.com.vn/gw/v1/public/bff-before-order/pis-online/paybill/query-partner
    
    Payload format:
    {
        "providerCode": "Payoo",
        "contractNumber": "PA22040428573",
        "sku": "00906819",
        "shopAddress": "string",
        "employeeCode": "string",
        "shopCode": "string"
    }
    
    Response format:
    {
        "status": 200,
        "message": "success",
        "data": {
            "totalContractAmount": 197910,
            "bills": [{
                "billId": "940120190",
                "partnerGroupCode": "DIEN",
                "partnerProductCode": "EVNNPC",
                "month": "12/2025",
                "moneyAmount": 197910,
                "contractNumber": "PA22040428573",
                "customerName": "Bùi Thị Bông",
                "address": "..."
            }]
        }
    }
    """
    try:
        # FPT Shop real API endpoint
        api_url = "https://papi.fptshop.com.vn/gw/v1/public/bff-before-order/pis-online/paybill/query-partner"
        
        # Map provider to FPT Shop SKU codes
        # SKU codes are specific product codes for each EVN region (confirmed)
        FPTSHOP_SKU_MAP = {
            'evn_south': '00906815',     # EVN miền Nam (SPC) ✓
            'evn_north': '00906819',     # EVN miền Bắc (NPC) ✓
            'evn_central': '00906817',   # EVN miền Trung (CPC) ✓
            'evn_hcm': '00906818',       # EVN TP.HCM ✓
            'evn_hanoi': '00906820'      # EVN Hà Nội ✓
        }
        
        fpt_sku = FPTSHOP_SKU_MAP.get(provider, '00906815')  # Default to EVN miền Nam
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Language': 'vi',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Origin': 'https://fptshop.com.vn',
            'Referer': 'https://fptshop.com.vn/',
            'order-channel': '1',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site'
        }
        
        # FPT Shop API payload format - exact format from browser
        payload = {
            "providerCode": "Payoo",
            "contractNumber": customer_code,
            "sku": fpt_sku,
            "shopAddress": "string",
            "employeeCode": "string",
            "shopCode": "string"
        }
        
        logger.info(f"FPTShop API: {api_url}")
        logger.info(f"FPTShop Payload: {payload}")
        
        # Get proxy from pool if enabled
        from services.proxy_service import get_proxy_for_request, report_proxy_result
        proxy_url = get_proxy_for_request()
        
        # Setup proxy for httpx (use 'proxy' param for newer httpx versions)
        proxy = None
        if proxy_url:
            logger.info(f"FPTShop using proxy: {proxy_url[:30]}...")
            proxy = proxy_url
        
        # Use http2=False to avoid issues, and let httpx handle decompression automatically
        async with httpx.AsyncClient(timeout=30.0, verify=False, proxy=proxy) as client:
            response = await client.post(api_url, json=payload, headers=headers)
            
            logger.info(f"FPTShop Response status: {response.status_code}")
            logger.info(f"FPTShop Response headers: {dict(response.headers)}")
            
            # Handle gzip/compressed response manually if needed
            import gzip
            import zlib
            
            try:
                # First try to get text directly (httpx should auto-decompress)
                response_text = response.text
            except Exception as decode_err:
                logger.warning(f"FPTShop decode error, trying manual decompress: {decode_err}")
                # Manual decompression for gzip
                content_encoding = response.headers.get('content-encoding', '').lower()
                raw_content = response.content
                
                if content_encoding == 'gzip' or (len(raw_content) > 2 and raw_content[:2] == b'\x1f\x8b'):
                    # Gzip compressed
                    response_text = gzip.decompress(raw_content).decode('utf-8')
                elif content_encoding == 'deflate':
                    # Deflate compressed
                    response_text = zlib.decompress(raw_content).decode('utf-8')
                elif content_encoding == 'br':
                    # Brotli compressed - try import brotli
                    try:
                        import brotli
                        response_text = brotli.decompress(raw_content).decode('utf-8')
                    except ImportError:
                        response_text = raw_content.decode('utf-8', errors='replace')
                else:
                    response_text = raw_content.decode('utf-8', errors='replace')
            
            logger.info(f"FPTShop Response body: {response_text[:500] if response_text else 'empty'}")
            
            # FPT Shop API returns 200 even for errors, check response content
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.info(f"FPTShop Result: {str(result)[:500]}")
                    
                    # FPT Shop response format:
                    # Success: {"status": 200, "message": "success", "data": {"totalContractAmount": 197910, "bills": [...]}}
                    # Error: {"status": 400, "error": {"code": "...", "message": "..."}}
                    
                    api_status = result.get('status', 0)
                    
                    if api_status == 200:
                        # Success - parse bill data
                        data = result.get('data', {})
                        
                        # Get bills array from response
                        bills = data.get('bills', [])
                        
                        # Extract customer info from first bill if available
                        customer_name = f"Mã {customer_code}"
                        address = ""
                        period = ""
                        
                        if bills and isinstance(bills, list) and len(bills) > 0:
                            first_bill = bills[0]
                            customer_name = first_bill.get('customerName', '') or f"Mã {customer_code}"
                            address = first_bill.get('address', '') or ''
                            period = first_bill.get('month', '') or ''
                        
                        # Extract total amount - use totalContractAmount from data
                        total_amount = data.get('totalContractAmount', 0) or data.get('totalAmountIncludingFee', 0)
                        if isinstance(total_amount, str):
                            total_amount = int(total_amount.replace(',', '').replace('.', ''))
                        
                        # Fallback: sum up from bills array if totalContractAmount is 0
                        if total_amount == 0 and bills:
                            for bill in bills:
                                amt = bill.get('moneyAmount', 0) or bill.get('amount', 0)
                                if isinstance(amt, str):
                                    amt = int(amt.replace(',', '').replace('.', ''))
                                total_amount += amt
                        
                        if not period:
                            period = datetime.now().strftime("%m/%Y")
                        
                        # Mark proxy as successful
                        if proxy_url:
                            report_proxy_result(proxy_url, True)
                        
                        return {
                            "success": True,
                            "source": "fptshop",
                            "customer_code": customer_code,
                            "customer_name": customer_name,
                            "address": address,
                            "total_amount": total_amount,
                            "period": period,
                            "status": "pending" if total_amount > 0 else "paid",
                            "provider": provider,
                            "raw_data": data
                        }
                    
                    elif api_status == 400:
                        # Error response from FPT Shop
                        error_info = result.get('error', {})
                        error_code = error_info.get('code', '')
                        error_msg = error_info.get('message', '') or error_info.get('details', '') or 'Lỗi không xác định'
                        
                        # Special handling for reCAPTCHA required (rate limit)
                        if 'RECAPTCHA' in error_code.upper() or 'too many requests' in error_msg.lower():
                            # Mark proxy as failed (rate limited)
                            if proxy_url:
                                report_proxy_result(proxy_url, False)
                            
                            return {
                                "success": False,
                                "source": "fptshop",
                                "customer_code": customer_code,
                                "customer_name": f"(Mã {customer_code})",
                                "address": "⚠️ FPT Shop yêu cầu CAPTCHA - Vui lòng chuyển sang Cổng 1 (EVN)",
                                "total_amount": 0,
                                "period": "-",
                                "status": "rate_limited",
                                "provider": provider,
                                "error_code": "RATE_LIMITED",
                                "need_fallback": True
                            }
                        
                        # Special handling for "không nợ cước"
                        if 'không nợ cước' in error_msg.lower():
                            return {
                                "success": True,
                                "source": "fptshop",
                                "customer_code": customer_code,
                                "customer_name": f"Mã {customer_code}",
                                "address": "Khách hàng không nợ cước",
                                "total_amount": 0,
                                "period": datetime.now().strftime("%m/%Y"),
                                "status": "paid",
                                "provider": provider
                            }
                        
                        return {
                            "success": False,
                            "source": "fptshop",
                            "customer_code": customer_code,
                            "customer_name": f"(Mã {customer_code})",
                            "address": error_msg,
                            "total_amount": 0,
                            "status": "not_found" if 'không hợp lệ' in error_msg.lower() else "error",
                            "provider": provider,
                            "error_code": error_code
                        }
                    
                    else:
                        # Other status codes
                        return {
                            "success": False,
                            "source": "fptshop",
                            "customer_code": customer_code,
                            "customer_name": f"(Mã {customer_code})",
                            "address": f"API trả về status: {api_status}",
                            "total_amount": 0,
                            "status": "error",
                            "provider": provider
                        }
                        
                except Exception as e:
                    logger.error(f"FPTShop parse error: {e}")
                    return {
                        "success": False,
                        "source": "fptshop",
                        "customer_code": customer_code,
                        "customer_name": f"(Mã {customer_code})",
                        "address": f"Lỗi parse response: {str(e)}",
                        "total_amount": 0,
                        "status": "error",
                        "provider": provider
                    }
            
            elif response.status_code == 400:
                # HTTP 400 - Parse JSON to check for specific errors
                try:
                    result = response.json()
                    error_info = result.get('error', {})
                    error_code = error_info.get('code', '')
                    error_details = error_info.get('details', '') or error_info.get('message', '') or 'Lỗi không xác định'
                    
                    logger.warning(f"FPTShop API 400 error: {error_code} - {error_details}")
                    
                    # Check for reCAPTCHA required (rate limit)
                    if 'RECAPTCHA' in error_code.upper() or 'too many requests' in error_details.lower():
                        return {
                            "success": False,
                            "source": "fptshop",
                            "customer_code": customer_code,
                            "customer_name": f"(Mã {customer_code})",
                            "address": "⚠️ FPT Shop yêu cầu CAPTCHA - Chuyển sang Cổng 1 (EVN)",
                            "total_amount": 0,
                            "period": "-",
                            "status": "rate_limited",
                            "provider": provider,
                            "error_code": "RATE_LIMITED",
                            "need_fallback": True
                        }
                    
                    # Check for "không nợ cước" or similar
                    if 'không nợ cước' in error_details.lower():
                        return {
                            "success": True,
                            "source": "fptshop",
                            "customer_code": customer_code,
                            "customer_name": f"Mã {customer_code}",
                            "address": "Khách hàng không nợ cước",
                            "total_amount": 0,
                            "period": datetime.now().strftime("%m/%Y"),
                            "status": "paid",
                            "provider": provider
                        }
                    
                    # Other 400 errors
                    return {
                        "success": False,
                        "source": "fptshop",
                        "customer_code": customer_code,
                        "customer_name": f"(Mã {customer_code})",
                        "address": error_details,
                        "total_amount": 0,
                        "status": "error",
                        "provider": provider,
                        "error_code": error_code
                    }
                except Exception as e:
                    logger.error(f"FPTShop 400 parse error: {e}")
                    return {
                        "success": False,
                        "source": "fptshop",
                        "customer_code": customer_code,
                        "customer_name": f"(Mã {customer_code})",
                        "address": f"Lỗi HTTP 400: {response_text[:100] if response_text else 'empty'}",
                        "total_amount": 0,
                        "status": "error",
                        "provider": provider
                    }
            
            elif response.status_code == 404:
                return {
                    "success": False,
                    "source": "fptshop",
                    "customer_code": customer_code,
                    "customer_name": f"(Mã {customer_code})",
                    "address": "API endpoint không tồn tại",
                    "total_amount": 0,
                    "status": "error",
                    "provider": provider
                }
            else:
                logger.warning(f"FPTShop API error: {response.status_code}")
                return {
                    "success": False,
                    "source": "fptshop",
                    "customer_code": customer_code,
                    "customer_name": f"(Mã {customer_code})",
                    "address": f"Lỗi HTTP: {response.status_code}",
                    "total_amount": 0,
                    "status": "error",
                    "provider": provider
                }
                
    except httpx.TimeoutException:
        logger.warning(f"FPTShop API timeout for: {customer_code}")
        return {
            "success": False,
            "source": "fptshop",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": "API timeout - thử lại sau",
            "total_amount": 0,
            "status": "timeout",
            "provider": provider
        }
    except Exception as e:
        logger.error(f"FPTShop lookup error: {e}")
        return {
            "success": False,
            "source": "fptshop",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": f"Lỗi: {str(e)}",
            "total_amount": 0,
            "status": "error",
            "provider": provider
        }


async def _lookup_via_evn_direct(customer_code: str, provider: str, db: Session):
    """
    Direct EVN API lookup as fallback for FPT Shop
    """
    try:
        # EVN direct lookup APIs
        EVN_APIS = {
            'evn_south': 'https://cskh.evnspc.vn/TraCuu/TraCuuTienDien',
            'evn_north': 'https://cskh.npc.com.vn/TraCuu/TraCuuTienDien',
            'evn_central': 'https://cskh.cpc.vn/TraCuu/TraCuuTienDien',
            'evn_hcm': 'https://cskh.evnhcmc.vn/TraCuu/TraCuuTienDien',
            'evn_hanoi': 'https://evnhanoi.vn/TraCuu/TraCuuTienDien'
        }
        
        base_url = EVN_APIS.get(provider, EVN_APIS['evn_south'])
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json, text/html, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        payload = {
            'MaKhachHang': customer_code
        }
        
        logger.info(f"EVN Direct API: {base_url}")
        
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(base_url, data=payload, headers=headers)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    if result.get('success') or result.get('TrangThai') == 1:
                        data = result.get('Data', {}) or result.get('data', {})
                        
                        return {
                            "success": True,
                            "source": "evn_direct",
                            "customer_code": customer_code,
                            "customer_name": data.get('TenKhachHang', '') or data.get('HoTen', '') or f"Mã {customer_code}",
                            "address": data.get('DiaChi', '') or '',
                            "total_amount": data.get('SoTien', 0) or data.get('TongTien', 0) or 0,
                            "period": data.get('KyHoaDon', '') or datetime.now().strftime("%m/%Y"),
                            "status": "pending",
                            "provider": provider
                        }
                except Exception:
                    pass
        
        # If all else fails, return error
        return {
            "success": False,
            "source": "fptshop",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": "Không thể tra cứu qua Cổng 2. Vui lòng thử Cổng 1 (DailyShopee)",
            "total_amount": 0,
            "status": "error",
            "provider": provider
        }
        
    except Exception as e:
        logger.error(f"EVN direct lookup error: {e}")
        return {
            "success": False,
            "source": "fptshop",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": f"Lỗi Cổng 2: {str(e)}",
            "total_amount": 0,
            "status": "error",
            "provider": provider
        }


async def _lookup_via_dailyshopee(customer_code: str, provider: str, db: Session):
    """
    Lookup electricity bill via DailyShopee API (Cổng 1)
    Supported providers with product_id:
    - evn_hcm: 175 (Điện Hồ Chí Minh)
    - evn_south: 187 (Điện Miền Nam)
    - evn_hanoi: 174 (Điện Hà Nội)
    - evn_central: 1593 (Điện Miền Trung)
    """
    try:
        # DailyShopee product_id mapping
        DAILYSHOPEE_PRODUCT_MAP = {
            'evn_hcm': '175',       # Điện Hồ Chí Minh
            'evn_south': '187',     # Điện Miền Nam
            'evn_hanoi': '174',     # Điện Hà Nội
            'evn_central': '1593'   # Điện Miền Trung
        }
        product_id = DAILYSHOPEE_PRODUCT_MAP.get(provider, '187')  # Default to Miền Nam
        
        # Get credentials from DailyShopee session if available
        cookie = ""
        csrf_token = ""
        try:
            from routers.system import get_dailyshopee_credentials
            ds_creds = get_dailyshopee_credentials()
            cookie = ds_creds.get("cookie", "") or settings.BILL_API_COOKIE
            csrf_token = ds_creds.get("csrf_token", "") or settings.BILL_API_CSRF_TOKEN
        except Exception as e:
            logger.warning(f"Failed to get DS credentials: {e}")
            cookie = settings.BILL_API_COOKIE
            csrf_token = settings.BILL_API_CSRF_TOKEN
        
        # Check if we have valid cookie
        if not cookie or len(cookie) < 20:
            logger.warning(f"No valid cookie available for DailyShopee")
            return {
                "success": False,
                "source": "dailyshopee",
                "customer_code": customer_code,
                "customer_name": f"(Mã {customer_code})",
                "address": "Chưa đăng nhập DailyShopee. Vui lòng nhấn 'Đăng nhập API' để kết nối.",
                "total_amount": 0,
                "status": "auth_required",
                "provider": provider
            }
        
        # Call external API
        api_url = f"{settings.BILL_API_BASE_URL}{settings.BILL_API_PATH}"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Origin': 'https://web.dailyshopee.vn',
            'Referer': 'https://web.dailyshopee.vn/'
        }
        
        if csrf_token:
            headers['X-Csrf-Token'] = csrf_token
        
        # DailyShopee API payload format - uses product_id not SKU
        payload = {
            "customer_code": customer_code,
            "product_id": product_id
        }
        
        logger.info(f"DailyShopee API: {api_url}")
        logger.info(f"Payload: {payload}")
        logger.info(f"Cookie length: {len(cookie)}, has CSRF: {bool(csrf_token)}")
        
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(api_url, json=payload, headers=headers)
            
            logger.info(f"DailyShopee Response status: {response.status_code}")
            logger.info(f"DailyShopee Response body: {response.text[:500] if response.text else 'empty'}")
            
            if response.status_code == 200:
                # Try to parse JSON response
                try:
                    response_text = response.text
                    if not response_text.strip():
                        logger.warning(f"Empty API response - cookie may be invalid")
                        return {
                            "success": False,
                            "source": "dailyshopee",
                            "customer_code": customer_code,
                            "customer_name": f"(Mã {customer_code})",
                            "address": "API trả về rỗng - Cookie có thể hết hạn",
                            "total_amount": 0,
                            "status": "auth_error",
                            "provider": provider,
                            "error": "Cookie hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại DailyShopee."
                        }
                    
                    result = response.json()
                    logger.info(f"DailyShopee Result: {str(result)[:300]}")
                except Exception as parse_err:
                    logger.error(f"JSON parse error: {parse_err}, response: {response.text[:500]}")
                    return {
                        "success": False,
                        "source": "dailyshopee",
                        "customer_code": customer_code,
                        "customer_name": f"(Mã {customer_code})",
                        "address": "Lỗi đọc response từ API",
                        "total_amount": 0,
                        "status": "error",
                        "provider": provider
                    }
                
                # Parse API response
                if result.get('error') == 0 or result.get('code') == 0 or result.get('success'):
                    bill_data = result.get('data', {})
                    
                    customer_name = bill_data.get('customer_name', '') or bill_data.get('name', '') or bill_data.get('ten_kh', '') or f"Mã {customer_code}"
                    address = bill_data.get('address', '') or bill_data.get('customer_address', '') or bill_data.get('dia_chi', '') or ''
                    
                    total_amount = 0
                    bills = bill_data.get('bills', []) or bill_data.get('list', [])
                    if bills and isinstance(bills, list):
                        for bill in bills:
                            amount = bill.get('amount', 0) or bill.get('total', 0) or bill.get('money', 0) or bill.get('so_tien', 0)
                            if isinstance(amount, str):
                                amount = int(amount.replace(',', '').replace('.', ''))
                            total_amount += amount
                    else:
                        total_amount = bill_data.get('amount', 0) or bill_data.get('total_amount', 0) or bill_data.get('money', 0) or bill_data.get('so_tien', 0)
                        if isinstance(total_amount, str):
                            total_amount = int(total_amount.replace(',', '').replace('.', ''))
                    
                    period = bill_data.get('period', '') or bill_data.get('billing_period', '') or bill_data.get('ky_hd', '') or datetime.now().strftime("%m/%Y")
                    
                    return {
                        "success": True,
                        "source": "dailyshopee",
                        "customer_code": customer_code,
                        "customer_name": customer_name,
                        "address": address,
                        "total_amount": total_amount,
                        "period": period,
                        "status": "pending" if total_amount > 0 else "paid",
                        "provider": provider,
                        "raw_data": bill_data
                    }
                else:
                    error_msg = result.get('message', '') or result.get('msg', '') or result.get('error_msg', '') or 'Không tìm thấy thông tin'
                    return {
                        "success": False,
                        "source": "dailyshopee",
                        "customer_code": customer_code,
                        "customer_name": f"(Mã {customer_code})",
                        "address": error_msg,
                        "total_amount": 0,
                        "status": "not_found",
                        "provider": provider
                    }
            elif response.status_code == 401:
                logger.warning("DailyShopee API returned 401 - authentication failed")
                return {
                    "success": False,
                    "source": "dailyshopee",
                    "customer_code": customer_code,
                    "customer_name": f"(Mã {customer_code})",
                    "address": "Cookie hết hạn. Vui lòng đăng nhập lại.",
                    "total_amount": 0,
                    "status": "auth_error",
                    "provider": provider
                }
            else:
                logger.warning(f"DailyShopee API returned status {response.status_code}: {response.text[:200]}")
                return {
                    "success": False,
                    "source": "dailyshopee",
                    "customer_code": customer_code,
                    "customer_name": f"(Mã {customer_code})",
                    "address": f"Lỗi API: {response.status_code}",
                    "total_amount": 0,
                    "status": "error",
                    "provider": provider
                }
                
    except httpx.TimeoutException:
        logger.warning(f"DailyShopee API timeout for customer_code: {customer_code}")
        return {
            "success": False,
            "source": "dailyshopee",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": "API timeout - thử lại sau",
            "total_amount": 0,
            "status": "timeout",
            "provider": provider
        }
    except httpx.RequestError as e:
        logger.warning(f"DailyShopee API request error for customer_code: {customer_code}: {e}")
        return {
            "success": False,
            "source": "dailyshopee",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": f"Lỗi kết nối: {str(e)}",
            "total_amount": 0,
            "status": "error",
            "provider": provider
        }
    except Exception as e:
        logger.error(f"DailyShopee lookup error: {e}")
        return {
            "success": False,
            "source": "dailyshopee",
            "customer_code": customer_code,
            "customer_name": f"(Mã {customer_code})",
            "address": f"Lỗi: {str(e)}",
            "total_amount": 0,
            "status": "error",
            "provider": provider
        }


@router.post("/bulk-import")
@manager_or_admin()
async def bulk_import_bills(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk import bills from lookup results into the system.
    """
    try:
        bills_data = data.get('bills', [])
        
        if not bills_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không có hóa đơn để nhập"
            )
        
        imported = 0
        skipped = 0
        errors = []
        bill_codes = []
        
        for bill_data in bills_data:
            try:
                customer_code = bill_data.get('customer_code', '').strip()
                if not customer_code:
                    skipped += 1
                    continue
                
                # Check if bill already exists
                existing = db.query(Bill).filter(
                    Bill.customer_code == customer_code,
                    Bill.period == datetime.now().strftime("%m/%Y")
                ).first()
                
                if existing:
                    skipped += 1
                    errors.append(f"Mã {customer_code}: Đã tồn tại trong kỳ này")
                    continue
                
                # Generate bill code
                bill_code = generate_bill_code(db)
                
                # Create new bill
                new_bill = Bill(
                    bill_code=bill_code,
                    customer_code=customer_code,
                    customer_name=bill_data.get('customer_name', '-'),
                    customer_address=bill_data.get('address', ''),
                    period=datetime.now().strftime("%m/%Y"),
                    total_amount=Decimal(str(bill_data.get('total_amount', 0))),
                    electricity_amount=Decimal(str(bill_data.get('total_amount', 0))),
                    status='in_stock',
                    created_by_id=current_user.id,
                    notes=f"Nhập từ tra cứu hàng loạt - Provider: {bill_data.get('provider', 'evn_south')}"
                )
                
                db.add(new_bill)
                db.commit()
                
                imported += 1
                bill_codes.append(bill_code)
                
            except Exception as e:
                skipped += 1
                errors.append(f"Mã {bill_data.get('customer_code', 'N/A')}: {str(e)}")
                db.rollback()
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="import",
            action="Nhập hóa đơn hàng loạt",
            details=f"Đã nhập {imported}/{len(bills_data)} hóa đơn từ tra cứu hàng loạt"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Bulk import: {imported}/{len(bills_data)} bills by {current_user.username}")
        
        return {
            "success": True,
            "message": f"Đã nhập {imported}/{len(bills_data)} hóa đơn",
            "imported": imported,
            "skipped": skipped,
            "total": len(bills_data),
            "errors": errors[:10],  # Limit errors returned
            "bill_codes": bill_codes[:20]  # Limit bill codes returned
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi nhập kho: {str(e)}"
        )


@router.get("/{bill_id}")
async def get_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bill details by ID
    """
    try:
        bill = db.query(Bill).options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer),
            joinedload(Bill.creator)
        ).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Check permissions
        if current_user.role == UserRole.AGENT:
            agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
            if agent and bill.agent_id != agent.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Build response with additional fields
        result = {
            "id": bill.id,
            "bill_code": bill.bill_code,
            "customer_id": bill.customer_id,
            "customer_code": bill.customer_code,
            "customer_name": bill.customer_name,
            "customer_address": bill.customer_address,
            "customer_phone": bill.customer_phone,
            "evn_customer_code": bill.evn_customer_code,
            "period": bill.period,
            "due_date": bill.due_date.isoformat() if bill.due_date else None,
            "total_amount": float(bill.total_amount) if bill.total_amount else 0,
            "electricity_amount": float(bill.electricity_amount) if bill.electricity_amount else 0,
            "vat_amount": float(bill.vat_amount) if bill.vat_amount else 0,
            "other_fees": float(bill.other_fees) if bill.other_fees else 0,
            "consumption": float(bill.consumption) if bill.consumption else None,
            "previous_index": float(bill.previous_index) if bill.previous_index else None,
            "current_index": float(bill.current_index) if bill.current_index else None,
            "agent_id": bill.agent_id,
            "agent_commission": float(bill.agent_commission) if bill.agent_commission else 0,
            "status": bill.status.value if bill.status else "in_stock",
            "payment_date": bill.payment_date.isoformat() if bill.payment_date else None,
            "created_by_id": bill.created_by_id,
            "created_by": bill.creator.full_name if bill.creator else "System",
            "imported_file": bill.imported_file,
            "imported_at": bill.imported_at.isoformat() if bill.imported_at else None,
            "evn_bill_code": bill.evn_bill_code,
            "payment_method": bill.payment_method,
            "transaction_ref": bill.transaction_ref,
            "notes": bill.notes,
            "provider": bill.bill_metadata.get("provider") if bill.bill_metadata else None,
            "created_at": bill.created_at.isoformat() if bill.created_at else None,
            "updated_at": bill.updated_at.isoformat() if bill.updated_at else None,
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy chi tiết hóa đơn"
        )

@router.post("", response_model=BillResponse)
async def create_bill(
    bill_data: BillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new bill
    """
    try:
        # Validate bill data
        errors = validate_bill_data(bill_data.dict())
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors)
            )
        
        # Generate bill code
        bill_code = generate_bill_code(db)
        
        # Check if customer exists
        customer = None
        if bill_data.customer_code:
            customer = db.query(Customer).filter(
                Customer.customer_code == bill_data.customer_code
            ).first()
        
        # Create bill
        bill = Bill(
            bill_code=bill_code,
            customer_id=customer.id if customer else None,
            customer_code=bill_data.customer_code,
            customer_name=bill_data.customer_name,
            customer_address=bill_data.customer_address,
            customer_phone=bill_data.customer_phone,
            evn_customer_code=bill_data.evn_customer_code,
            period=bill_data.period,
            due_date=bill_data.due_date,
            total_amount=bill_data.total_amount,
            electricity_amount=bill_data.electricity_amount,
            vat_amount=bill_data.vat_amount or Decimal('0'),
            other_fees=bill_data.other_fees or Decimal('0'),
            consumption=bill_data.consumption,
            previous_index=bill_data.previous_index,
            current_index=bill_data.current_index,
            agent_id=bill_data.agent_id,
            status=bill_data.status,
            evn_bill_code=bill_data.evn_bill_code,
            notes=bill_data.notes,
            created_by_id=current_user.id,
            imported_file=bill_data.imported_file
        )
        
        db.add(bill)
        db.commit()
        db.refresh(bill)
        
        # Create activity log
        create_bill_activity_log(
            db, current_user.id,
            "Bill created",
            bill.id,
            f"Created bill {bill_code} for customer {bill_data.customer_code}"
        )
        
        logger.info(f"Bill created: {bill_code} by {current_user.username}")
        
        # Get full bill details
        bill = db.query(Bill).options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer),
            joinedload(Bill.creator)
        ).filter(Bill.id == bill.id).first()
        
        return bill
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạo hóa đơn"
        )

@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: int,
    bill_data: BillUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update bill information
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Check permissions
        if current_user.role == UserRole.AGENT:
            agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
            if not agent or bill.agent_id != agent.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Can't update paid bills
        if bill.status == BillStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể cập nhật hóa đơn đã thanh toán"
            )
        
        # Validate data if updating period
        if bill_data.period:
            if not ValidationUtils.validate_bill_period(bill_data.period):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Định dạng kỳ không hợp lệ. Phải là YYYY-MM"
                )
        
        # Update bill fields
        update_fields = {}
        for field, value in bill_data.dict(exclude_unset=True).items():
            if value is not None:
                setattr(bill, field, value)
                update_fields[field] = value
        
        bill.updated_at = datetime.utcnow()
        db.commit()
        
        # Create activity log
        if update_fields:
            create_bill_activity_log(
                db, current_user.id,
                "Bill updated",
                bill.id,
                f"Updated fields: {', '.join(update_fields.keys())}"
            )
        
        logger.info(f"Bill updated: {bill.bill_code} by {current_user.username}")
        
        # Get updated bill details
        bill = db.query(Bill).options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer),
            joinedload(Bill.creator)
        ).filter(Bill.id == bill_id).first()
        
        return bill
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật hóa đơn"
        )

@router.post("/{bill_id}/assign/{agent_id}")
async def assign_bill(
    bill_id: int,
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign bill to agent
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Check bill status
        if bill.status != BillStatus.IN_STOCK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hóa đơn đã ở trạng thái {bill.status.value}"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ quản lý và admin mới được gán hóa đơn"
            )
        
        # Assign bill to agent
        success = assign_bill_to_agent(db, bill, agent_id, current_user)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể gán hóa đơn cho đại lý. Đại lý có thể không hoạt động hoặc số dư không đủ."
            )
        
        logger.info(f"Bill assigned: {bill.bill_code} to agent {agent_id} by {current_user.username}")
        
        return SuccessResponse(
            message="Bill assigned to agent successfully",
            data={
                "bill_id": bill.id,
                "bill_code": bill.bill_code,
                "agent_id": agent_id,
                "status": bill.status.value,
                "commission": float(bill.agent_commission)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Assign bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể gán hóa đơn"
        )

@router.post("/{bill_id}/purchase")
async def purchase_bill(
    bill_id: int,
    current_agent: Agent = Depends(get_current_active_agent),
    db: Session = Depends(get_db)
):
    """
    Agent purchases a bill (self-assign)
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Check bill status
        if bill.status != BillStatus.IN_STOCK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hóa đơn đã ở trạng thái {bill.status.value}"
            )
        
        # Check if agent has sufficient balance
        if current_agent.available_balance < bill.total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số dư không đủ"
            )
        
        # Check per transaction limit
        if bill.total_amount > current_agent.per_transaction_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số tiền hóa đơn vượt quá giới hạn mỗi giao dịch: {FormatUtils.format_currency(current_agent.per_transaction_limit)}"
            )
        
        # Check daily limit
        today_transactions = current_agent.get_today_transactions_total(db)
        if today_transactions + bill.total_amount > current_agent.daily_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Giao dịch sẽ vượt quá giới hạn hàng ngày: {FormatUtils.format_currency(current_agent.daily_limit)}"
            )
        
        # Purchase bill
        success = assign_bill_to_agent(db, bill, current_agent.id, current_agent.user)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể mua hóa đơn"
            )
        
        logger.info(f"Bill purchased: {bill.bill_code} by agent {current_agent.agent_code}")
        
        return SuccessResponse(
            message="Bill purchased successfully",
            data={
                "bill_id": bill.id,
                "bill_code": bill.bill_code,
                "amount": float(bill.total_amount),
                "commission": float(bill.agent_commission),
                "remaining_balance": float(current_agent.available_balance)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Purchase bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể mua hóa đơn"
        )

@router.post("/{bill_id}/pay")
async def pay_bill(
    bill_id: int,
    payment_method: str = "cash",
    transaction_ref: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark bill as paid
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Check bill status
        if bill.status != BillStatus.SOLD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hóa đơn phải được bán trước khi thanh toán. Trạng thái hiện tại: {bill.status.value}"
            )
        
        # Check permissions
        if current_user.role == UserRole.AGENT:
            agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
            if not agent or bill.agent_id != agent.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Process payment
        transaction = process_bill_payment(
            db, bill, payment_method, transaction_ref or "", current_user
        )
        
        # Unfreeze agent balance and deduct payment
        if bill.agent_id:
            agent = db.query(Agent).filter(Agent.id == bill.agent_id).first()
            if agent:
                agent.frozen_balance -= bill.total_amount
                agent.balance -= bill.total_amount
                agent.updated_at = datetime.utcnow()
                
                # Pay commission if any
                if bill.agent_commission > 0:
                    agent.balance += bill.agent_commission
                    agent.total_commission += bill.agent_commission
                    
                    # Mark commission as paid
                    commission_log = db.query(CommissionLog).filter(
                        CommissionLog.bill_id == bill.id,
                        CommissionLog.agent_id == agent.id
                    ).first()
                    
                    if commission_log:
                        commission_log.is_paid = True
                        commission_log.paid_at = datetime.utcnow()
                        commission_log.payment_transaction_id = transaction.id
        
        db.commit()
        
        # Create activity log
        create_bill_activity_log(
            db, current_user.id,
            "Bill paid",
            bill.id,
            f"Bill paid via {payment_method}. Amount: {FormatUtils.format_currency(bill.total_amount)}"
        )
        
        logger.info(f"Bill paid: {bill.bill_code} by {current_user.username}")
        
        return SuccessResponse(
            message="Bill payment processed successfully",
            data={
                "bill_id": bill.id,
                "bill_code": bill.bill_code,
                "amount": float(bill.total_amount),
                "payment_method": payment_method,
                "transaction_ref": transaction_ref,
                "payment_date": bill.payment_date.isoformat(),
                "transaction_code": transaction.transaction_code
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Pay bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xử lý thanh toán hóa đơn"
        )

@router.post("/{bill_id}/cancel")
async def cancel_bill(
    bill_id: int,
    reason: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a bill
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Check bill status
        if bill.status == BillStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể hủy hóa đơn đã thanh toán"
            )
        
        if bill.status == BillStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hóa đơn đã bị hủy"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ quản lý và admin mới được hủy hóa đơn"
            )
        
        # If bill was assigned to agent, unfreeze balance
        if bill.agent_id and bill.status == BillStatus.SOLD:
            agent = db.query(Agent).filter(Agent.id == bill.agent_id).first()
            if agent:
                agent.frozen_balance -= bill.total_amount
                agent.updated_at = datetime.utcnow()
        
        # Update bill status
        previous_status = bill.status.value
        bill.status = BillStatus.CANCELLED
        bill.notes = f"{bill.notes or ''}\nCancelled by {current_user.username}. Reason: {reason}"
        bill.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Create activity log
        create_bill_activity_log(
            db, current_user.id,
            "Bill cancelled",
            bill.id,
            f"Bill cancelled from {previous_status}. Reason: {reason}"
        )
        
        logger.warning(f"Bill cancelled: {bill.bill_code} by {current_user.username}. Reason: {reason}")
        
        return SuccessResponse(
            message="Bill cancelled successfully",
            data={
                "bill_id": bill.id,
                "bill_code": bill.bill_code,
                "previous_status": previous_status,
                "current_status": bill.status.value,
                "reason": reason,
                "cancelled_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Cancel bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể hủy hóa đơn"
        )

@router.delete("/{bill_id}")
@manager_or_admin()
async def delete_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Soft delete a bill - move to history with cancelled status
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        original_code = bill.bill_code
        
        # Soft delete: move to history (cancelled status)
        bill.status = BillStatus.CANCELLED
        bill.notes = f"{bill.notes or ''}\nĐã xóa bởi {current_user.username} vào {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
        bill.updated_at = datetime.utcnow()
        db.commit()
        
        # Create activity log
        create_bill_activity_log(
            db, current_user.id,
            "Bill deleted",
            bill.id,
            f"Bill {original_code} moved to history"
        )
        
        logger.warning(f"Bill deleted: {original_code} by {current_user.username}")
        
        return SuccessResponse(
            message="Đã chuyển hóa đơn sang lịch sử",
            data={
                "bill_id": bill.id,
                "original_code": original_code,
                "deleted_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xóa hóa đơn"
        )

@router.delete("/{bill_id}/permanent")
@manager_or_admin()
async def permanent_delete_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete a bill from database (hard delete)
    Only for bills already in cancelled/deleted status
    """
    try:
        # Get bill
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy hóa đơn"
            )
        
        # Only allow permanent delete for cancelled bills
        if bill.status != BillStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể xóa vĩnh viễn các hóa đơn đã ở trạng thái Đã xóa"
            )
        
        original_code = bill.bill_code
        original_customer = bill.customer_name
        
        # Create activity log before deletion
        create_bill_activity_log(
            db, current_user.id,
            "Bill permanently deleted",
            bill.id,
            f"Bill {original_code} permanently deleted from database"
        )
        
        # Hard delete - remove from database
        db.delete(bill)
        db.commit()
        
        logger.warning(f"Bill permanently deleted: {original_code} (customer: {original_customer}) by {current_user.username}")
        
        return SuccessResponse(
            message="Đã xóa vĩnh viễn hóa đơn khỏi hệ thống",
            data={
                "bill_id": bill_id,
                "original_code": original_code,
                "customer_name": original_customer,
                "deleted_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Permanent delete bill error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xóa vĩnh viễn hóa đơn"
        )

@router.post("/import")
@manager_or_admin()
async def import_bills(
    file: UploadFile = File(...),
    agent_id: Optional[int] = None,
    override: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Import bills from Excel or CSV file
    """
    try:
        # Validate file
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ hỗ trợ file Excel (.xlsx, .xls) và CSV"
            )
        
        # Save uploaded file
        upload_dir = Path(settings.UPLOAD_DIR) / "imports"
        result = await FileUtils.save_upload_file(file, upload_dir)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Không thể lưu file")
            )
        
        # Record file upload
        uploaded_file = UploadedFile(
            user_id=current_user.id,
            filename=result["filename"],
            original_filename=file.filename,
            file_path=result["file_path"],
            file_size=result["file_size"],
            mime_type=result["mime_type"],
            upload_type="bill_import"
        )
        
        db.add(uploaded_file)
        db.commit()
        
        # Import bills based on file type
        if file.filename.endswith('.csv'):
            import_result = await ImportUtils.import_bills_from_csv(
                result["file_path"], db, current_user.id, agent_id
            )
        else:
            import_result = await ImportUtils.import_bills_from_excel(
                result["file_path"], db, current_user.id, agent_id
            )
        
        # Update uploaded file record
        uploaded_file.status = "completed" if import_result["success"] else "failed"
        uploaded_file.processed_at = datetime.utcnow()
        uploaded_file.processed_count = import_result.get("imported", 0)
        uploaded_file.error_count = import_result.get("skipped", 0)
        uploaded_file.error_log = "\n".join(import_result.get("errors", []))[:4000]  # Limit length
        
        db.commit()
        
        if not import_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=import_result.get("error", "Nhập dữ liệu thất bại")
            )
        
        # Create activity log
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="import",
            action="Imported bills",
            details=f"Imported {import_result['imported']} bills from file: {file.filename}"
        )
        db.add(activity)
        db.commit()
        
        # Send notification email in background
        if background_tasks and import_result["imported"] > 0:
            background_tasks.add_task(
                send_import_notification,
                current_user,
                import_result
            )
        
        logger.info(f"Bills imported: {import_result['imported']} bills by {current_user.username}")
        
        return BillImportResponse(
            success=True,
            total=import_result["total"],
            imported=import_result["imported"],
            skipped=import_result["skipped"],
            errors=import_result.get("errors", []),
            bill_codes=import_result.get("bill_codes", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Import bills error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể nhập hóa đơn"
        )

@router.post("/export")
@manager_or_admin()
async def export_bills(
    filters: Dict = Depends(bill_filter_params),
    format: str = Query("excel", regex="^(excel|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export bills to Excel or CSV
    """
    try:
        # Get bills
        query = get_bill_query(db, filters)
        bills = query.options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer),
            joinedload(Bill.creator)
        ).order_by(Bill.created_at.desc()).all()
        
        # Prepare data
        data = []
        for bill in bills:
            data.append({
                "Mã hóa đơn": bill.bill_code,
                "Mã khách hàng": bill.customer_code,
                "Tên khách hàng": bill.customer_name,
                "Địa chỉ": bill.customer_address,
                "Số điện thoại": bill.customer_phone,
                "Kỳ thanh toán": bill.period,
                "Ngày đến hạn": FormatUtils.format_date(bill.due_date) if bill.due_date else "",
                "Tổng tiền": float(bill.total_amount),
                "Tiền điện": float(bill.electricity_amount),
                "VAT": float(bill.vat_amount),
                "Phí khác": float(bill.other_fees),
                "Sản lượng (kWh)": float(bill.consumption) if bill.consumption else "",
                "Trạng thái": bill.status.value,
                "Đại lý": bill.agent.user.full_name if bill.agent else "",
                "Mã đại lý": bill.agent.agent_code if bill.agent else "",
                "Hoa hồng đại lý": float(bill.agent_commission),
                "Ngày tạo": FormatUtils.format_datetime(bill.created_at),
                "Ngày thanh toán": FormatUtils.format_datetime(bill.payment_date) if bill.payment_date else "",
                "Phương thức thanh toán": bill.payment_method,
                "Ghi chú": bill.notes
            })
        
        # Export to file
        if format == "excel":
            file_path = ExportUtils.export_to_excel(data, "bills_export")
        else:
            file_path = ExportUtils.export_to_csv(data, "bills_export")
        
        # Create activity log
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="export",
            action="Exported bills",
            details=f"Exported {len(bills)} bills to {format.upper()}"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Bills exported: {len(bills)} bills to {format} by {current_user.username}")
        
        # Build correct download URL
        file_name = Path(file_path).name
        download_url = f"/static/uploads/exports/{file_name}"
        
        return SuccessResponse(
            message=f"Exported {len(bills)} bills successfully",
            data={
                "file_path": file_path,
                "bill_count": len(bills),
                "format": format,
                "download_url": download_url
            }
        )
        
    except Exception as e:
        logger.error(f"Export bills error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xuất hóa đơn"
        )

@router.get("/overdue", response_model=PaginatedResponse)
async def get_overdue_bills(
    pagination: Dict = Depends(pagination_params),
    days_overdue: int = Query(1, ge=1, description="Minimum days overdue"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overdue bills
    """
    try:
        # Calculate cutoff date
        cutoff_date = date.today() - timedelta(days=days_overdue)
        
        # Build query
        query = db.query(Bill).filter(
            Bill.status.in_([BillStatus.IN_STOCK, BillStatus.PENDING]),
            Bill.due_date < cutoff_date
        )
        
        # If user is agent, only show their bills
        if current_user.role == UserRole.AGENT:
            agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
            if agent:
                query = query.filter(Bill.agent_id == agent.id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        
        bills = query.options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer)
        ).order_by(
            Bill.due_date.asc()
        ).offset((page - 1) * limit).limit(limit).all()
        
        # Calculate overdue amounts
        total_overdue = db.query(func.sum(Bill.total_amount)).filter(
            Bill.status.in_([BillStatus.IN_STOCK, BillStatus.PENDING]),
            Bill.due_date < date.today()
        ).scalar() or Decimal('0')
        
        return PaginatedResponse(
            page=page,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=bills,
            summary={
                "total_overdue": float(total_overdue),
                "overdue_count": total,
                "cutoff_date": cutoff_date.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Get overdue bills error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách hóa đơn quá hạn"
        )

@router.get("/report/summary")
@manager_or_admin()
async def get_bills_summary_report(
    date_range: DateRange,
    group_by: str = Query("day", regex="^(day|week|month|year)$"),
    agent_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bills summary report
    """
    try:
        # Build base query
        query = db.query(Bill).filter(
            Bill.payment_date.between(date_range.start_date, date_range.end_date),
            Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
        )
        
        if agent_id:
            query = query.filter(Bill.agent_id == agent_id)
        
        # Group by period
        if group_by == "day":
            period_expr = func.date(Bill.payment_date)
        elif group_by == "week":
            period_expr = func.date_trunc('week', Bill.payment_date)
        elif group_by == "month":
            period_expr = func.date_trunc('month', Bill.payment_date)
        else:  # year
            period_expr = func.date_trunc('year', Bill.payment_date)
        
        # Execute query
        results = db.query(
            period_expr.label("period"),
            func.count(Bill.id).label("bill_count"),
            func.sum(Bill.total_amount).label("total_amount"),
            func.sum(Bill.agent_commission).label("total_commission"),
            func.avg(Bill.total_amount).label("avg_amount")
        ).filter(
            Bill.payment_date.between(date_range.start_date, date_range.end_date),
            Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
        ).group_by(
            period_expr
        ).order_by(
            period_expr
        ).all()
        
        # Prepare response
        items = []
        for period, bill_count, total_amount, total_commission, avg_amount in results:
            items.append({
                "period": period.strftime("%Y-%m-%d") if group_by == "day" else period.strftime("%Y-%m"),
                "total_amount": float(total_amount) if total_amount else 0,
                "total_bills": bill_count,
                "total_commission": float(total_commission) if total_commission else 0,
                "avg_amount": float(avg_amount) if avg_amount else 0
            })
        
        # Calculate totals
        total_bills = sum(item["total_bills"] for item in items)
        total_amount = sum(item["total_amount"] for item in items)
        total_commission = sum(item["total_commission"] for item in items)
        
        return ReportResponse(
            report_type="bills_summary",
            date_range=date_range,
            total_amount=Decimal(str(total_amount)),
            total_bills=total_bills,
            total_commission=Decimal(str(total_commission)),
            items=items,
            summary={
                "group_by": group_by,
                "average_daily_sales": total_amount / max(len(items), 1),
                "agent_id": agent_id
            }
        )
        
    except Exception as e:
        logger.error(f"Get bills summary report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạo báo cáo tổng hợp hóa đơn"
        )

@router.get("/search")
async def search_bills(
    q: str = Query(..., min_length=2, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search bills by various criteria
    """
    try:
        search_term = f"%{q}%"
        
        # Build query
        query = db.query(Bill).filter(
            or_(
                Bill.bill_code.ilike(search_term),
                Bill.customer_code.ilike(search_term),
                Bill.customer_name.ilike(search_term),
                Bill.customer_phone.ilike(search_term),
                Bill.evn_customer_code.ilike(search_term),
                Bill.evn_bill_code.ilike(search_term)
            )
        )
        
        # If user is agent, only show their bills
        if current_user.role == UserRole.AGENT:
            agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
            if agent:
                query = query.filter(Bill.agent_id == agent.id)
        
        # Limit results
        bills = query.options(
            joinedload(Bill.agent).joinedload(Agent.user),
            joinedload(Bill.customer)
        ).order_by(
            Bill.created_at.desc()
        ).limit(20).all()
        
        return {
            "success": True,
            "query": q,
            "results": bills,
            "count": len(bills)
        }
        
    except Exception as e:
        logger.error(f"Search bills error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tìm kiếm hóa đơn"
        )

# Health check endpoint
@router.get("/health")
async def bills_health():
    """
    Bills service health check
    """
    return {
        "status": "healthy",
        "service": "bills",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "public": ["/", "/{id}", "/search"],
            "agent": ["/purchase", "/pay"],
            "manager": ["/import", "/export", "/report/*", "/stats", "/overdue", "/lookup", "/bulk-import"],
            "admin": ["/assign", "/cancel", "/delete"]
        }
    }

# Helper function for notifications
async def send_import_notification(user: User, import_result: Dict[str, Any]):
    """Send import notification email"""
    try:
        subject = f"Kết quả nhập hóa đơn: {import_result['imported']}/{import_result['total']}"
        
        body = f"""
        Xin chào {user.full_name},
        
        Quá trình nhập hóa đơn của bạn đã hoàn thành.
        
        Kết quả:
        - Tổng số bản ghi: {import_result['total']}
        - Thành công: {import_result['imported']}
        - Bỏ qua: {import_result['skipped']}
        
        {f"Các mã hóa đơn đã nhập: {', '.join(import_result.get('bill_codes', [])[:10])}{'...' if len(import_result.get('bill_codes', [])) > 10 else ''}" if import_result.get('bill_codes') else ""}
        
        {f"Lỗi: {chr(10).join(import_result.get('errors', [])[:5])}{'...' if len(import_result.get('errors', [])) > 5 else ''}" if import_result.get('errors') else ""}
        
        Trân trọng,
        Đội ngũ 7TY.VN
        """
        
        EmailUtils.send_email(user.email, subject, body)
        
    except Exception as e:
        logger.error(f"Failed to send import notification: {e}")

# Helper function for CSV imports (to be added to ImportUtils)
async def import_bills_from_csv(file_path: str, db: Session, created_by_id: int, agent_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Import bills from CSV file
    """
    try:
        # Read CSV file
        df = pd.read_csv(file_path)
        
        # Validate required columns
        required_columns = ['customer_code', 'customer_name', 'period', 'total_amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                "success": False,
                "error": f"Missing required columns: {', '.join(missing_columns)}"
            }
        
        imported = 0
        skipped = 0
        errors = []
        bill_codes = []
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Validate data
                row_errors = validate_bill_data(row.to_dict())
                if row_errors:
                    skipped += 1
                    errors.append(f"Row {index + 2}: {'; '.join(row_errors)}")
                    continue
                
                # Check if bill already exists for this period and customer
                existing_bill = db.query(Bill).filter(
                    Bill.customer_code == str(row['customer_code']),
                    Bill.period == str(row['period'])
                ).first()
                
                if existing_bill:
                    skipped += 1
                    errors.append(f"Row {index + 2}: Bill already exists for customer {row['customer_code']} period {row['period']}")
                    continue
                
                # Generate bill code
                bill_code = generate_bill_code(db)
                
                # Check if customer exists
                customer = db.query(Customer).filter(
                    Customer.customer_code == str(row['customer_code'])
                ).first()
                
                # Create bill
                bill = Bill(
                    bill_code=bill_code,
                    customer_id=customer.id if customer else None,
                    customer_code=str(row['customer_code']),
                    customer_name=str(row['customer_name']),
                    customer_address=row.get('customer_address'),
                    customer_phone=row.get('customer_phone'),
                    evn_customer_code=row.get('evn_customer_code'),
                    period=str(row['period']),
                    due_date=pd.to_datetime(row['due_date']).date() if 'due_date' in row and pd.notna(row['due_date']) else None,
                    total_amount=Decimal(str(row['total_amount'])),
                    electricity_amount=Decimal(str(row.get('electricity_amount', row['total_amount']))),
                    vat_amount=Decimal(str(row.get('vat_amount', 0))),
                    other_fees=Decimal(str(row.get('other_fees', 0))),
                    consumption=Decimal(str(row['consumption'])) if 'consumption' in row and pd.notna(row['consumption']) else None,
                    previous_index=Decimal(str(row['previous_index'])) if 'previous_index' in row and pd.notna(row['previous_index']) else None,
                    current_index=Decimal(str(row['current_index'])) if 'current_index' in row and pd.notna(row['current_index']) else None,
                    agent_id=agent_id,
                    status='in_stock',
                    evn_bill_code=row.get('evn_bill_code'),
                    notes=row.get('notes'),
                    created_by_id=created_by_id,
                    imported_file=file_path
                )
                
                db.add(bill)
                db.commit()
                
                imported += 1
                bill_codes.append(bill_code)
                
            except Exception as e:
                skipped += 1
                errors.append(f"Row {index + 2}: {str(e)}")
                db.rollback()
                continue
        
        return {
            "success": True,
            "total": len(df),
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "bill_codes": bill_codes
        }
        
    except Exception as e:
        logger.error(f"Error importing bills from CSV: {e}")
        return {
            "success": False,
            "error": str(e)
        }




