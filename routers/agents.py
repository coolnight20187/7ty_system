from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import logging
import asyncio
from decimal import Decimal
from pathlib import Path
import pandas as pd

from config import settings
from database import get_db, paginate_query
from dependencies import (
    get_current_user, get_current_active_user, get_current_active_admin, require_role, manager_or_admin, 
    admin_only, pagination_params, agent_filter_params
)
from models import (
    User, UserRole, Agent, AgentType, AgentStatus, ActivityType,
    Bill, BillStatus, Transaction, TransactionType, TransactionStatus,
    Customer, ActivityLog, CommissionLog
)
from schemas import (
    AgentBase, AgentCreate, AgentCreateWithUser, AgentUpdate, AgentResponse,
    AgentStatsResponse, PaginatedResponse, SuccessResponse,
    ErrorResponse, DateRange, ReportResponse, UserResponse,
    DepositRequest
)
from utils import (
    FormatUtils, ValidationUtils, FileUtils, ExportUtils,
    ImportUtils, EmailUtils, CacheUtils, SecurityUtils,
    generate_transaction_code
)

# Import WebSocket manager for real-time notifications
from routers.websocket import manager as ws_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Agents"])

# Helper functions
def get_agent_query(db: Session, filters: Dict[str, Any] = None):
    """Build query for agents with filters"""
    query = db.query(Agent).join(User, Agent.user_id == User.id).filter(
        User.is_deleted == False
    )
    
    if not filters:
        return query
    
    # Apply filters
    if filters.get("status"):
        query = query.filter(Agent.status == filters["status"])
    
    if filters.get("agent_type"):
        query = query.filter(Agent.agent_type == filters["agent_type"])
    
    if filters.get("search"):
        search_term = f"%{filters['search']}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                Agent.agent_code.ilike(search_term),
                User.phone.ilike(search_term),
                Agent.company_name.ilike(search_term)
            )
        )
    
    if filters.get("created_from"):
        query = query.filter(Agent.created_at >= filters["created_from"])
    
    if filters.get("created_to"):
        query = query.filter(Agent.created_at <= filters["created_to"])
    
    return query

def calculate_agent_stats(db: Session, agent_id: int) -> Dict[str, Any]:
    """Calculate agent statistics"""
    # Today's date
    today = date.today()
    
    # Today's sales
    today_sales = db.query(func.sum(Bill.total_amount)).filter(
        Bill.agent_id == agent_id,
        Bill.status.in_([BillStatus.SOLD, BillStatus.PAID]),
        func.date(Bill.payment_date) == today
    ).scalar() or Decimal('0')
    
    # Today's bills count
    today_bills = db.query(func.count(Bill.id)).filter(
        Bill.agent_id == agent_id,
        Bill.status.in_([BillStatus.SOLD, BillStatus.PAID]),
        func.date(Bill.payment_date) == today
    ).scalar() or 0
    
    # Total customers
    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.agent_id == agent_id,
        Customer.is_active == True
    ).scalar() or 0
    
    # Success rate (bills sold / total bills assigned)
    total_assigned_bills = db.query(func.count(Bill.id)).filter(
        Bill.agent_id == agent_id
    ).scalar() or 0
    
    total_sold_bills = db.query(func.count(Bill.id)).filter(
        Bill.agent_id == agent_id,
        Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
    ).scalar() or 0
    
    success_rate = Decimal('0')
    if total_assigned_bills > 0:
        success_rate = (Decimal(total_sold_bills) / Decimal(total_assigned_bills)) * 100
    
    return {
        "today_sales": today_sales,
        "today_bills": today_bills,
        "total_customers": total_customers,
        "success_rate": success_rate,
        "total_assigned_bills": total_assigned_bills,
        "total_sold_bills": total_sold_bills
    }

def create_agent_activity_log(
    db: Session, 
    user_id: int, 
    action: str, 
    agent_id: int, 
    details: str = None
):
    """Create activity log for agent actions"""
    activity = ActivityLog(
        user_id=user_id,
        activity_type="update",
        action=action,
        resource_type="agent",
        resource_id=agent_id,
        details=details
    )
    db.add(activity)
    db.commit()

# Routes

@router.get("/{agent_id}/images", response_model=Dict[str, Any])
async def get_agent_images(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get agent document images (CCCD, store photos) from database.
    Returns Base64 encoded images that can be displayed directly in HTML.
    """
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions - Admin/Manager can view all, agents can view their own
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xem ảnh của đại lý này"
                )
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_code": agent.agent_code,
            "images": {
                "cccd_front": {
                    "filename": agent.cccd_front_path,
                    "data": agent.cccd_front_data  # Base64 data URI
                },
                "cccd_back": {
                    "filename": agent.cccd_back_path,
                    "data": agent.cccd_back_data
                },
                "store_image_1": {
                    "filename": agent.store_image_1_path,
                    "data": agent.store_image_1_data
                },
                "store_image_2": {
                    "filename": agent.store_image_2_path,
                    "data": agent.store_image_2_data
                },
                "store_image_3": {
                    "filename": agent.store_image_3_path,
                    "data": agent.store_image_3_data
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent images error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy ảnh đại lý"
        )


@router.get("/me", response_model=AgentResponse)
async def get_current_agent(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's agent profile.
    Accessible by users who have an active Agent record linked to their account.
    """
    # Get agent info linked to this user
    agent = db.query(Agent).options(
        joinedload(Agent.user)
    ).filter(Agent.user_id == current_user.id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản chưa được kích hoạt Đại Lý"
        )
    
    return agent


@router.post("/change-password")
async def change_agent_password(
    password_data: Dict[str, str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Đổi mật khẩu đăng nhập cho đại lý
    """
    current_password = password_data.get("current_password")
    new_password = password_data.get("new_password")
    
    if not current_password or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp mật khẩu hiện tại và mật khẩu mới"
        )
    
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải có ít nhất 6 ký tự"
        )
    
    # Verify current password
    if not SecurityUtils.verify_password(current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không đúng"
        )
    
    # Update password
    current_user.password_hash = SecurityUtils.hash_password(new_password)
    current_user.updated_at = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"Agent {current_user.id} changed password successfully")
    
    return {
        "success": True,
        "message": "Đổi mật khẩu thành công"
    }


@router.post("/by-user/{user_id}/activate")
@manager_or_admin()
async def activate_agent_by_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Activate or create agent for a user
    """
    try:
        # Check if user exists
        user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if agent already exists
        agent = db.query(Agent).filter(Agent.user_id == user_id).first()
        
        if agent:
            # Activate existing agent
            agent.status = AgentStatus.ACTIVE
            db.commit()
            return {"message": "Agent activated", "agent_id": agent.id}
        else:
            # Create new agent
            agent_code = f"AG{user_id:06d}"
            new_agent = Agent(
                user_id=user_id,
                agent_code=agent_code,
                agent_name=user.full_name or user.username,
                agent_type=AgentType.INDIVIDUAL,
                status=AgentStatus.ACTIVE,
                balance=0,
                commission_rate=0.05
            )
            db.add(new_agent)
            db.commit()
            db.refresh(new_agent)
            return {"message": "Agent created and activated", "agent_id": new_agent.id}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activate agent error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/by-user/{user_id}/deactivate")
@manager_or_admin()
async def deactivate_agent_by_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate agent for a user
    """
    try:
        agent = db.query(Agent).filter(Agent.user_id == user_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent.status = AgentStatus.INACTIVE
        db.commit()
        return {"message": "Agent deactivated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate agent error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=Dict[str, Any])
@manager_or_admin()
async def get_agents(
    pagination: Dict = Depends(pagination_params),
    filters: Dict = Depends(agent_filter_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of agents with pagination and filtering
    """
    try:
        # Build query
        query = get_agent_query(db, filters)
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        sort_by = pagination.get("sort_by") or "created_at"
        sort_order = pagination.get("sort_order", "desc")
        
        if sort_by == "full_name":
            sort_column = User.full_name
        elif sort_by == "balance":
            sort_column = Agent.balance
        elif sort_by == "total_sales":
            sort_column = Agent.total_sales
        else:
            sort_column = getattr(Agent, sort_by, Agent.created_at)
        
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        agents = query.offset((page - 1) * limit).limit(limit).all()
        
        # Prepare response data with pending deposits count
        agent_responses = []
        for agent in agents:
            # Count pending deposit requests for this agent
            pending_deposits = db.query(func.count(Transaction.id)).filter(
                Transaction.agent_id == agent.id,
                Transaction.transaction_type == TransactionType.DEPOSIT,
                Transaction.status == TransactionStatus.PENDING
            ).scalar() or 0
            
            user_response = {
                "id": agent.user.id,
                "username": agent.user.username,
                "email": agent.user.email,
                "full_name": agent.user.full_name,
                "phone": agent.user.phone,
                "role": agent.user.role,
                "is_active": agent.user.is_active,
                "avatar_url": agent.user.avatar_url,
                "created_at": agent.user.created_at
            } if agent.user else None
            
            agent_dict = {
                "id": agent.id,
                "user_id": agent.user_id,
                "agent_code": agent.agent_code,
                "agent_name": agent.agent_name,
                "company_name": agent.company_name,
                "tax_code": agent.tax_code,
                "address": agent.address,
                "city": agent.city,
                "district": agent.district,
                "ward": agent.ward,
                "agent_type": agent.agent_type,
                "status": agent.status,
                "commission_rate": agent.commission_rate,
                "balance": agent.balance,
                "user": user_response,
                "created_at": agent.created_at,
                "updated_at": agent.updated_at,
                "approved_at": agent.approved_at,
                "approved_by": agent.approved_by_id,
                "pending_deposits": pending_deposits
            }
            agent_responses.append(agent_dict)
        
        # Sort: agents with pending deposits first
        agent_responses.sort(key=lambda x: x.get('pending_deposits', 0), reverse=True)
        
        total_pages = (total + limit - 1) // limit
        return {
            "data": agent_responses,
            "page": page,
            "limit": limit,
            "total": total,
            "pages": total_pages
        }
        
    except Exception as e:
        logger.error(f"Get agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách đại lý"
        )

@router.get("/stats", response_model=Dict[str, Any])
@manager_or_admin()
async def get_agents_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get agents statistics overview
    """
    try:
        # Total agents
        total_agents = db.query(Agent).count()
        
        # Agents by status
        status_counts = db.query(
            Agent.status, func.count(Agent.id)
        ).group_by(Agent.status).all()
        
        # Agents by type
        type_counts = db.query(
            Agent.agent_type, func.count(Agent.id)
        ).group_by(Agent.agent_type).all()
        
        # Active agents (with sales in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_agents = db.query(func.count(distinct(Bill.agent_id))).filter(
            Bill.agent_id.isnot(None),
            Bill.payment_date >= thirty_days_ago,
            Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
        ).scalar() or 0
        
        # Total balance
        total_balance = db.query(func.sum(Agent.balance)).scalar() or Decimal('0')
        
        # Total frozen balance
        total_frozen = db.query(func.sum(Agent.frozen_balance)).scalar() or Decimal('0')
        
        # Total sales (last 30 days)
        total_sales_30d = db.query(func.sum(Bill.total_amount)).filter(
            Bill.agent_id.isnot(None),
            Bill.payment_date >= thirty_days_ago,
            Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
        ).scalar() or Decimal('0')
        
        # Pending approval count
        pending_approval = db.query(func.count(Agent.id)).filter(
            Agent.status == AgentStatus.PENDING
        ).scalar() or 0
        
        return {
            "success": True,
            "stats": {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "pending_approval": pending_approval,
                "total_balance": float(total_balance),
                "total_frozen_balance": float(total_frozen),
                "total_sales_30d": float(total_sales_30d),
                "by_status": {status.value: count for status, count in status_counts},
                "by_type": {agent_type.value: count for agent_type, count in type_counts}
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Get agents stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy thống kê đại lý"
        )

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get agent details by ID
    """
    try:
        # Get agent with user info and approved_by
        agent = db.query(Agent).options(
            joinedload(Agent.user),
            joinedload(Agent.approved_by)
        ).filter(
            Agent.id == agent_id
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Get agent stats
        stats = calculate_agent_stats(db, agent_id)
        
        # Prepare response with approved_by_user
        # Remove relationship objects from __dict__ to avoid conflicts
        agent_data = {k: v for k, v in agent.__dict__.items() if not k.startswith('_') and k != 'approved_by'}
        agent_data["user"] = agent.user
        agent_data["approved_by"] = agent.approved_by_id  # Use the ID, not the object
        agent_data["approved_by_user"] = agent.approved_by  # User object for display
        agent_data["stats"] = stats
        
        return AgentResponse(**agent_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy thông tin đại lý"
        )

@router.post("/with-user", response_model=AgentResponse)
@manager_or_admin()
async def create_agent_with_user(
    agent_data: AgentCreateWithUser,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new agent with user account in one step (Manager or Admin only)
    This endpoint creates both the user account and agent record atomically
    """
    try:
        logger.info(f"Creating agent with user: {agent_data.username}")
        
        # Auto-generate email (not provided in new schema)
        import time
        timestamp = int(time.time() * 1000)
        auto_email = f"{agent_data.username}.{timestamp}@7ty.vn"
        logger.info(f"Email auto-generated: {auto_email}")
        
        # Check if username already exists
        existing_user = db.query(User).filter(
            User.username == agent_data.username
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên đăng nhập đã tồn tại. Vui lòng sử dụng tên đăng nhập khác."
            )
        
        # Check if phone already exists
        if agent_data.phone:
            existing_phone = db.query(User).filter(
                User.phone == agent_data.phone
            ).first()
            
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại đã được đăng ký. Vui lòng sử dụng số điện thoại khác."
                )
        
        # Check if agent code already exists
        existing_code = db.query(Agent).filter(
            Agent.agent_code == agent_data.agent_code
        ).first()
        
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã đại lý đã tồn tại"
            )
        
        # Create user first
        logger.info(f"Hashing password for user {agent_data.username}")
        try:
            hashed_password = SecurityUtils.get_password_hash(agent_data.password)
        except ValueError as e:
            if "72" in str(e):
                # Force truncate password and retry
                logger.warning(f"Password too long, truncating: {str(e)}")
                truncated_pwd = agent_data.password[:72]
                hashed_password = SecurityUtils.get_password_hash(truncated_pwd)
            else:
                raise
        
        new_user = User(
            username=agent_data.username,
            email=auto_email,
            full_name=agent_data.full_name,
            phone=agent_data.phone,
            role=UserRole.AGENT,
            password_hash=hashed_password,
            is_active=True
        )
        
        db.add(new_user)
        db.flush()  # Get the user ID without committing
        logger.info(f"User created with ID: {new_user.id}")
        
        # Create agent record
        logger.info(f"Creating agent with code: {agent_data.agent_code}")
        new_agent = Agent(
            user_id=new_user.id,
            agent_code=agent_data.agent_code,
            agent_name=agent_data.agent_name,
            agent_type=agent_data.agent_type,
            company_name=agent_data.company_name,
            tax_code=agent_data.tax_code,
            address=agent_data.address,
            city=agent_data.city,
            district=agent_data.district,
            ward=agent_data.ward,
            status=agent_data.status,
            commission_rate=agent_data.commission_rate or Decimal('0'),
            balance=Decimal('0'),
            created_by_id=current_user.id
        )
        
        db.add(new_agent)
        db.commit()
        db.refresh(new_agent)
        logger.info(f"Agent created with ID: {new_agent.id}")
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.CREATE,
            action="create_agent_with_user",
            resource_type="agent",
            resource_id=new_agent.id,
            details=f"Created agent {new_agent.agent_code} with user {new_user.username}"
        )
        db.add(activity)
        db.commit()
        
        # Fetch fresh data to ensure all fields are populated
        db.refresh(new_agent)
        db.refresh(new_user)
        
        # Return response using ORM mode
        return AgentResponse.from_orm(new_agent)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create agent with user error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể tạo đại lý: {str(e)}"
        )

@router.post("/link", response_model=Dict[str, Any])
@manager_or_admin()
async def link_user_to_agent(
    user_id: int = Form(..., description="ID of existing user to link"),
    store_name: str = Form(..., description="Store name"),
    store_address: str = Form(..., description="Store address"),
    company_name: Optional[str] = Form(None, description="Company name"),
    tax_code: Optional[str] = Form(None, description="Tax code"),
    agent_type: str = Form("individual", description="Agent type: individual or company"),
    store_image_1: UploadFile = File(..., description="Store image 1"),
    store_image_2: Optional[UploadFile] = File(None, description="Store image 2"),
    store_image_3: Optional[UploadFile] = File(None, description="Store image 3"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Link an existing user account to a new agent
    This endpoint creates agent record for an existing user and saves store images
    """
    try:
        logger.info(f"Linking user {user_id} to new agent")
        
        # Get the user
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy tài khoản"
            )
        
        # Check if user already has an agent
        existing_agent = db.query(Agent).filter(
            Agent.user_id == user_id
        ).first()
        
        if existing_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tài khoản này đã liên kết với đại lý {existing_agent.agent_code}"
            )
        
        # Generate agent code with format AGxxxxxx
        last_agent = db.query(Agent).order_by(Agent.id.desc()).first()
        next_number = (last_agent.id + 1) if last_agent else 1
        agent_code = f"AG{next_number:06d}"
        
        # Read and encode images as Base64 for database storage
        import base64
        
        saved_files = {}
        image_data = {}
        
        # Read store image 1
        store_image_1_content = await store_image_1.read()
        store_image_1_b64 = base64.b64encode(store_image_1_content).decode('utf-8')
        store_image_1_ext = store_image_1.filename.split('.')[-1].lower() if '.' in store_image_1.filename else 'jpg'
        image_data["store_image_1"] = f"data:image/{store_image_1_ext};base64,{store_image_1_b64}"
        saved_files["store_image_1"] = f"store_1_{store_image_1.filename}"
        
        # Read store image 2 (optional)
        if store_image_2:
            store_image_2_content = await store_image_2.read()
            store_image_2_b64 = base64.b64encode(store_image_2_content).decode('utf-8')
            store_image_2_ext = store_image_2.filename.split('.')[-1].lower() if '.' in store_image_2.filename else 'jpg'
            image_data["store_image_2"] = f"data:image/{store_image_2_ext};base64,{store_image_2_b64}"
            saved_files["store_image_2"] = f"store_2_{store_image_2.filename}"
        
        # Read store image 3 (optional)
        if store_image_3:
            store_image_3_content = await store_image_3.read()
            store_image_3_b64 = base64.b64encode(store_image_3_content).decode('utf-8')
            store_image_3_ext = store_image_3.filename.split('.')[-1].lower() if '.' in store_image_3.filename else 'jpg'
            image_data["store_image_3"] = f"data:image/{store_image_3_ext};base64,{store_image_3_b64}"
            saved_files["store_image_3"] = f"store_3_{store_image_3.filename}"
        
        logger.info(f"Encoded {len(image_data)} store images for agent {agent_code}")
        
        # Update user role to AGENT
        user.role = UserRole.AGENT
        
        # Parse agent type
        agent_type_enum = AgentType.INDIVIDUAL if agent_type == "individual" else AgentType.COMPANY
        
        # Create agent record with image data stored in database
        new_agent = Agent(
            user_id=user.id,
            agent_code=agent_code,
            agent_name=store_name,
            agent_type=agent_type_enum,
            company_name=company_name,
            tax_code=tax_code,
            address=store_address,
            store_address=store_address,
            status=AgentStatus.PENDING,
            commission_rate=Decimal('0'),
            balance=Decimal('0'),
            created_by_id=current_user.id,
            # Store file names in path fields (for reference)
            store_image_1_path=saved_files.get('store_image_1'),
            store_image_2_path=saved_files.get('store_image_2'),
            store_image_3_path=saved_files.get('store_image_3'),
            # Store Base64 image data in database (persistent storage)
            store_image_1_data=image_data.get('store_image_1'),
            store_image_2_data=image_data.get('store_image_2'),
            store_image_3_data=image_data.get('store_image_3'),
            # Note about stored images
            approval_notes=f"Store images stored in database. Files: {', '.join(saved_files.values())}"
        )
        
        db.add(new_agent)
        db.commit()
        db.refresh(new_agent)
        logger.info(f"Agent created with ID: {new_agent.id}, code: {agent_code}, linked to user {user.username}")
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.CREATE,
            action="link_user_to_agent",
            resource_type="agent",
            resource_id=new_agent.id,
            details=f"Linked user {user.username} to agent {agent_code}"
        )
        db.add(activity)
        db.commit()
        
        return {
            "success": True,
            "message": "Đăng ký đại lý thành công! Vui lòng chờ duyệt.",
            "agent_code": agent_code,
            "agent_id": new_agent.id,
            "user_id": user.id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Link user to agent error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể đăng ký đại lý: {str(e)}"
        )

@router.post("/register", response_model=Dict[str, Any])
@manager_or_admin()
async def register_agent(
    phone: str = Form(..., description="Phone number (also used as username)"),
    password: str = Form(..., description="Password"),
    full_name: str = Form(..., description="Full name"),
    store_name: str = Form(..., description="Store name"),
    store_address: str = Form(..., description="Store address"),
    email: Optional[str] = Form(None, description="Email"),
    company_name: Optional[str] = Form(None, description="Company name"),
    agent_type: str = Form("individual", description="Agent type: individual or company"),
    cccd_front: UploadFile = File(..., description="Front of ID card"),
    cccd_back: UploadFile = File(..., description="Back of ID card"),
    store_image_1: UploadFile = File(..., description="Store image 1"),
    store_image_2: Optional[UploadFile] = File(None, description="Store image 2"),
    store_image_3: Optional[UploadFile] = File(None, description="Store image 3"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new agent with user account and file uploads
    This endpoint creates user account, agent record, and saves uploaded images
    """
    try:
        logger.info(f"Registering new agent with phone: {phone}")
        
        # Validate phone format
        if not phone or len(phone) != 10 or not phone.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại không hợp lệ (phải có 10 chữ số)"
            )
        
        # Use phone as username (remove leading 0)
        username = phone.lstrip('0') if phone.startswith('0') else phone
        
        # Always auto-generate unique email to avoid conflicts
        import time
        import random
        timestamp = int(time.time() * 1000)
        random_suffix = random.randint(1000, 9999)
        auto_email = f"{username}.{timestamp}.{random_suffix}@7ty.vn"
        
        # Check if username already exists
        existing_user = db.query(User).filter(
            User.username == username
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại này đã được đăng ký. Vui lòng sử dụng số điện thoại khác."
            )
        
        # Check if phone number already exists in another user
        existing_phone = db.query(User).filter(
            User.phone == phone
        ).first()
        
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại này đã được đăng ký cho tài khoản khác. Vui lòng sử dụng số điện thoại khác."
            )
        
        # Check if email already exists (if user provided email)
        if email:
            existing_email = db.query(User).filter(
                User.email == email
            ).first()
            
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email này đã được đăng ký. Vui lòng sử dụng email khác."
                )
            # Use provided email
            auto_email = email
        
        # Generate agent code with format AGxxxxxx
        # Get the next available agent code by counting existing agents
        last_agent = db.query(Agent).order_by(Agent.id.desc()).first()
        next_number = (last_agent.id + 1) if last_agent else 1
        agent_code = f"AG{next_number:06d}"  # Format: AGxxxxxx
        
        # Read and encode images as Base64 for database storage
        import base64
        
        saved_files = {}
        image_data = {}
        
        # Read CCCD front
        cccd_front_content = await cccd_front.read()
        cccd_front_b64 = base64.b64encode(cccd_front_content).decode('utf-8')
        cccd_front_ext = cccd_front.filename.split('.')[-1].lower() if '.' in cccd_front.filename else 'jpg'
        image_data["cccd_front"] = f"data:image/{cccd_front_ext};base64,{cccd_front_b64}"
        saved_files["cccd_front"] = f"cccd_front_{cccd_front.filename}"
        
        # Read CCCD back
        cccd_back_content = await cccd_back.read()
        cccd_back_b64 = base64.b64encode(cccd_back_content).decode('utf-8')
        cccd_back_ext = cccd_back.filename.split('.')[-1].lower() if '.' in cccd_back.filename else 'jpg'
        image_data["cccd_back"] = f"data:image/{cccd_back_ext};base64,{cccd_back_b64}"
        saved_files["cccd_back"] = f"cccd_back_{cccd_back.filename}"
        
        # Read store image 1
        store_image_1_content = await store_image_1.read()
        store_image_1_b64 = base64.b64encode(store_image_1_content).decode('utf-8')
        store_image_1_ext = store_image_1.filename.split('.')[-1].lower() if '.' in store_image_1.filename else 'jpg'
        image_data["store_image_1"] = f"data:image/{store_image_1_ext};base64,{store_image_1_b64}"
        saved_files["store_image_1"] = f"store_1_{store_image_1.filename}"
        
        # Read store image 2 (optional)
        if store_image_2:
            store_image_2_content = await store_image_2.read()
            store_image_2_b64 = base64.b64encode(store_image_2_content).decode('utf-8')
            store_image_2_ext = store_image_2.filename.split('.')[-1].lower() if '.' in store_image_2.filename else 'jpg'
            image_data["store_image_2"] = f"data:image/{store_image_2_ext};base64,{store_image_2_b64}"
            saved_files["store_image_2"] = f"store_2_{store_image_2.filename}"
        
        # Read store image 3 (optional)
        if store_image_3:
            store_image_3_content = await store_image_3.read()
            store_image_3_b64 = base64.b64encode(store_image_3_content).decode('utf-8')
            store_image_3_ext = store_image_3.filename.split('.')[-1].lower() if '.' in store_image_3.filename else 'jpg'
            image_data["store_image_3"] = f"data:image/{store_image_3_ext};base64,{store_image_3_b64}"
            saved_files["store_image_3"] = f"store_3_{store_image_3.filename}"
        
        logger.info(f"Encoded {len(image_data)} images for agent {agent_code}")
        
        # Hash password
        logger.info(f"Hashing password for user {username}")
        try:
            hashed_password = SecurityUtils.get_password_hash(password)
        except ValueError as e:
            if "72" in str(e):
                logger.warning(f"Password too long, truncating: {str(e)}")
                truncated_pwd = password[:72]
                hashed_password = SecurityUtils.get_password_hash(truncated_pwd)
            else:
                raise
        
        # Create user
        new_user = User(
            username=username,
            email=auto_email,
            full_name=full_name,
            phone=phone,
            role=UserRole.AGENT,
            password_hash=hashed_password,
            is_active=True
        )
        
        db.add(new_user)
        db.flush()
        logger.info(f"User created with ID: {new_user.id}")
        
        # Parse agent type
        agent_type_enum = AgentType.INDIVIDUAL if agent_type == "individual" else AgentType.COMPANY
        
        # Create agent record with image data stored in database
        new_agent = Agent(
            user_id=new_user.id,
            agent_code=agent_code,
            agent_name=store_name,
            agent_type=agent_type_enum,
            company_name=company_name,
            address=store_address,
            store_address=store_address,
            status=AgentStatus.PENDING,
            commission_rate=Decimal('0'),
            balance=Decimal('0'),
            created_by_id=current_user.id,
            # Store file names in path fields (for reference)
            cccd_front_path=saved_files.get('cccd_front'),
            cccd_back_path=saved_files.get('cccd_back'),
            store_image_1_path=saved_files.get('store_image_1'),
            store_image_2_path=saved_files.get('store_image_2'),
            store_image_3_path=saved_files.get('store_image_3'),
            # Store Base64 image data in database (persistent storage)
            cccd_front_data=image_data.get('cccd_front'),
            cccd_back_data=image_data.get('cccd_back'),
            store_image_1_data=image_data.get('store_image_1'),
            store_image_2_data=image_data.get('store_image_2'),
            store_image_3_data=image_data.get('store_image_3'),
            # Note about stored images
            approval_notes=f"Images stored in database. Files: {', '.join(saved_files.values())}"
        )
        
        db.add(new_agent)
        db.commit()
        db.refresh(new_agent)
        logger.info(f"Agent created with ID: {new_agent.id}, code: {agent_code}, images saved to database")
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.CREATE,
            action="register_agent",
            resource_type="agent",
            resource_id=new_agent.id,
            details=f"Registered agent {agent_code} with phone {phone}"
        )
        db.add(activity)
        db.commit()
        
        return {
            "success": True,
            "message": "Đăng ký đại lý thành công! Vui lòng chờ duyệt.",
            "agent_code": agent_code,
            "agent_id": new_agent.id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Register agent error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể đăng ký đại lý: {str(e)}"
        )

@router.post("", response_model=AgentResponse)
@manager_or_admin()
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new agent
    """
    try:
        # Check if user exists and is not already an agent
        user = db.query(User).filter(
            User.id == agent_data.user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )
        
        # Check if user is already an agent
        existing_agent = db.query(Agent).filter(
            Agent.user_id == agent_data.user_id
        ).first()
        
        if existing_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Người dùng đã là đại lý"
            )
        
        # Generate 6-digit agent code if not provided
        agent_code = agent_data.agent_code
        if not agent_code:
            # Get the next available agent code
            last_agent = db.query(Agent).order_by(Agent.id.desc()).first()
            next_number = (last_agent.id + 1) if last_agent else 1
            agent_code = f"{next_number:06d}"  # 6 digits, zero-padded
        
        # Check if agent code is unique
        existing_code = db.query(Agent).filter(
            Agent.agent_code == agent_code
        ).first()
        
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã đại lý đã tồn tại"
            )
        
        # Create agent
        agent = Agent(
            user_id=agent_data.user_id,
            agent_code=agent_code,
            company_name=agent_data.company_name,
            tax_code=agent_data.tax_code,
            agent_type=agent_data.agent_type,
            status=agent_data.status,
            commission_rate=agent_data.commission_rate,
            min_commission=agent_data.min_commission,
            max_commission=agent_data.max_commission,
            daily_limit=agent_data.daily_limit,
            per_transaction_limit=agent_data.per_transaction_limit,
            approved_by_id=current_user.id if agent_data.status == AgentStatus.ACTIVE else None,
            approved_at=datetime.utcnow() if agent_data.status == AgentStatus.ACTIVE else None,
            approval_notes=agent_data.approval_notes
        )
        
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        # Update user role to AGENT if not already
        if user.role != UserRole.AGENT:
            user.role = UserRole.AGENT
            db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent created",
            agent.id,
            f"Created agent {agent_code} with status {agent_data.status.value}"
        )
        
        # Send notification email to user
        if user.email and agent_data.status == AgentStatus.ACTIVE:
            try:
                EmailUtils.send_email(
                    to_email=user.email,
                    subject="Tài khoản đại lý đã được kích hoạt",
                    body=f"""
                    Xin chào {user.full_name},
                    
                    Tài khoản đại lý của bạn tại 7TY.VN đã được kích hoạt thành công.
                    
                    Thông tin đại lý:
                    - Mã đại lý: {agent_code}
                    - Loại đại lý: {agent_data.agent_type.value}
                    - Tỷ lệ hoa hồng: {agent_data.commission_rate}%
                    
                    Bạn có thể bắt đầu sử dụng hệ thống ngay bây giờ.
                    
                    Trân trọng,
                    Đội ngũ 7TY.VN
                    """
                )
            except Exception as email_error:
                logger.error(f"Failed to send activation email: {email_error}")
        
        logger.info(f"Agent created: {agent_code} by {current_user.username}")
        
        # Get agent with user info
        agent = db.query(Agent).options(joinedload(Agent.user)).filter(
            Agent.id == agent.id
        ).first()
        
        return AgentResponse(**{**agent.__dict__, "user": agent.user})
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Create agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạo đại lý"
        )

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update agent information
    """
    try:
        # Get agent
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Check if updating status to ACTIVE
        if agent_data.status and agent_data.status == AgentStatus.ACTIVE:
            if agent.status != AgentStatus.ACTIVE:
                agent.approved_by_id = current_user.id
                agent.approved_at = datetime.utcnow()
        
        # Update user.full_name if provided
        if agent_data.full_name:
            agent.user.full_name = agent_data.full_name
        
        # Update agent fields
        update_fields = {}
        for field, value in agent_data.dict(exclude_unset=True).items():
            if value is not None:
                # Skip full_name as it's handled separately for user
                if field == 'full_name':
                    continue
                setattr(agent, field, value)
                update_fields[field] = value
        
        agent.updated_at = datetime.utcnow()
        db.commit()
        
        # Create activity log
        if update_fields or agent_data.full_name:
            fields_updated = list(update_fields.keys())
            if agent_data.full_name:
                fields_updated.append('full_name')
            create_agent_activity_log(
                db, current_user.id,
                "Agent updated",
                agent.id,
                f"Updated fields: {', '.join(fields_updated)}"
            )
        
        logger.info(f"Agent updated: {agent.agent_code} by {current_user.username}")
        
        # Get updated agent with user info
        agent = db.query(Agent).options(joinedload(Agent.user)).filter(
            Agent.id == agent_id
        ).first()
        
        return AgentResponse(**{**agent.__dict__, "user": agent.user})
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật đại lý"
        )

@router.put("/{agent_id}/update-with-files", response_model=AgentResponse)
async def update_agent_with_files(
    agent_id: int,
    full_name: str = Form(None),
    email: str = Form(None),
    agent_type: str = Form(None),
    store_name: str = Form(None),
    company_name: str = Form(None),
    store_address: str = Form(None),
    new_password: str = Form(None),
    daily_limit: float = Form(None),
    per_transaction_limit: float = Form(None),
    agent_status: str = Form(None),
    commission_rate: float = Form(None),
    min_commission: float = Form(None),
    max_commission: float = Form(None),
    tax_code: str = Form(None),
    cccd_front: UploadFile = File(None),
    cccd_back: UploadFile = File(None),
    store_image_1: UploadFile = File(None),
    store_image_2: UploadFile = File(None),
    store_image_3: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update agent information with file uploads
    """
    try:
        # Get agent
        agent = db.query(Agent).options(joinedload(Agent.user)).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Note: Images are now saved as Base64 in database, no need for file system
        
        # Update user info
        if full_name and agent.user:
            agent.user.full_name = full_name
        if email and agent.user:
            agent.user.email = email
        
        # Update password if provided
        if new_password and len(new_password) >= 6 and agent.user:
            from security import get_password_hash
            agent.user.hashed_password = get_password_hash(new_password)
        
        # Update agent fields
        if agent_type:
            agent.agent_type = agent_type
        if store_name:
            agent.agent_name = store_name
        if company_name:
            agent.company_name = company_name
        if store_address:
            agent.store_address = store_address
        if daily_limit is not None:
            agent.daily_limit = daily_limit
        if per_transaction_limit is not None:
            agent.per_transaction_limit = per_transaction_limit
        
        # Update status if provided
        if agent_status:
            try:
                # Convert lowercase to uppercase for enum compatibility
                status_upper = agent_status.upper()
                agent.status = AgentStatus(status_upper)
                # If activating, set approved info
                if status_upper == 'ACTIVE' and not agent.approved_at:
                    agent.approved_at = datetime.utcnow()
                    agent.approved_by_id = current_user.id
                logger.info(f"Agent {agent.agent_code} status updated to {status_upper}")
            except ValueError as e:
                logger.warning(f"Invalid status value: {agent_status}, error: {e}")
        
        # Update commission settings
        if commission_rate is not None:
            agent.commission_rate = commission_rate
        if min_commission is not None:
            agent.min_commission = min_commission
        if max_commission is not None:
            agent.max_commission = max_commission
        if tax_code:
            agent.tax_code = tax_code
        
        # Save uploaded files as Base64 in database for persistence
        import base64
        
        if cccd_front and cccd_front.filename:
            content = await cccd_front.read()
            cccd_front_b64 = base64.b64encode(content).decode('utf-8')
            cccd_front_ext = cccd_front.filename.split('.')[-1].lower() if '.' in cccd_front.filename else 'jpg'
            agent.cccd_front_data = f"data:image/{cccd_front_ext};base64,{cccd_front_b64}"
            agent.cccd_front_path = f"cccd_front_{cccd_front.filename}"
            logger.info(f"Saved cccd_front to database for agent {agent.agent_code}")
        
        if cccd_back and cccd_back.filename:
            content = await cccd_back.read()
            cccd_back_b64 = base64.b64encode(content).decode('utf-8')
            cccd_back_ext = cccd_back.filename.split('.')[-1].lower() if '.' in cccd_back.filename else 'jpg'
            agent.cccd_back_data = f"data:image/{cccd_back_ext};base64,{cccd_back_b64}"
            agent.cccd_back_path = f"cccd_back_{cccd_back.filename}"
            logger.info(f"Saved cccd_back to database for agent {agent.agent_code}")
        
        if store_image_1 and store_image_1.filename:
            content = await store_image_1.read()
            store_image_1_b64 = base64.b64encode(content).decode('utf-8')
            store_image_1_ext = store_image_1.filename.split('.')[-1].lower() if '.' in store_image_1.filename else 'jpg'
            agent.store_image_1_data = f"data:image/{store_image_1_ext};base64,{store_image_1_b64}"
            agent.store_image_1_path = f"store_1_{store_image_1.filename}"
            logger.info(f"Saved store_image_1 to database for agent {agent.agent_code}")
        
        if store_image_2 and store_image_2.filename:
            content = await store_image_2.read()
            store_image_2_b64 = base64.b64encode(content).decode('utf-8')
            store_image_2_ext = store_image_2.filename.split('.')[-1].lower() if '.' in store_image_2.filename else 'jpg'
            agent.store_image_2_data = f"data:image/{store_image_2_ext};base64,{store_image_2_b64}"
            agent.store_image_2_path = f"store_2_{store_image_2.filename}"
            logger.info(f"Saved store_image_2 to database for agent {agent.agent_code}")
        
        if store_image_3 and store_image_3.filename:
            content = await store_image_3.read()
            store_image_3_b64 = base64.b64encode(content).decode('utf-8')
            store_image_3_ext = store_image_3.filename.split('.')[-1].lower() if '.' in store_image_3.filename else 'jpg'
            agent.store_image_3_data = f"data:image/{store_image_3_ext};base64,{store_image_3_b64}"
            agent.store_image_3_path = f"store_3_{store_image_3.filename}"
            logger.info(f"Saved store_image_3 to database for agent {agent.agent_code}")
        
        agent.updated_at = datetime.utcnow()
        db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent updated with files",
            agent.id,
            f"Agent {agent.agent_code} updated with new files"
        )
        
        logger.info(f"Agent updated with files: {agent.agent_code} by {current_user.username}")
        
        # Get updated agent with user info
        agent = db.query(Agent).options(joinedload(Agent.user)).filter(
            Agent.id == agent_id
        ).first()
        
        return AgentResponse(**{**agent.__dict__, "user": agent.user})
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Update agent with files error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật đại lý"
        )

@router.delete("/{agent_id}")
@admin_only()
async def delete_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent by ID (soft delete)"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Soft delete - mark user as deleted
        if agent.user:
            agent.user.is_deleted = True
        agent.is_deleted = True
        
        db.commit()
        
        logger.info(f"Agent {agent_id} deleted by user {current_user.id}")
        return {"message": "Agent deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xóa đại lý"
        )

@router.post("/{agent_id}/approve")
@manager_or_admin()
async def approve_agent(
    agent_id: int,
    commission_rate: Optional[float] = Query(None, description="Commission rate"),
    approval_notes: Optional[str] = Query(None, description="Approval notes"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve agent (change status to ACTIVE)
    """
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        if agent.status == AgentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đại lý đã được kích hoạt"
            )
        
        # Update agent status
        agent.status = AgentStatus.ACTIVE
        agent.approved_by_id = current_user.id
        agent.approved_at = datetime.utcnow()
        agent.approval_notes = approval_notes
        if commission_rate is not None:
            agent.commission_rate = Decimal(str(commission_rate))
        agent.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent approved",
            agent.id,
            f"Agent approved with notes: {approval_notes}"
        )
        
        # Send approval email to agent
        user = db.query(User).filter(User.id == agent.user_id).first()
        if user and user.email:
            try:
                EmailUtils.send_email(
                    to_email=user.email,
                    subject="Tài khoản đại lý đã được duyệt",
                    body=f"""
                    Xin chào {user.full_name},
                    
                    Tài khoản đại lý của bạn đã được duyệt và kích hoạt thành công.
                    
                    Thông tin đại lý:
                    - Mã đại lý: {agent.agent_code}
                    - Trạng thái: Hoạt động
                    - Ngày duyệt: {FormatUtils.format_datetime(agent.approved_at)}
                    
                    Bạn có thể bắt đầu sử dụng hệ thống ngay bây giờ.
                    
                    Trân trọng,
                    Đội ngũ 7TY.VN
                    """
                )
            except Exception as email_error:
                logger.error(f"Failed to send approval email: {email_error}")
        
        logger.info(f"Agent approved: {agent.agent_code} by {current_user.username}")
        
        return SuccessResponse(
            message="Agent approved successfully",
            data={
                "agent_id": agent.id,
                "agent_code": agent.agent_code,
                "status": agent.status.value,
                "approved_by": current_user.username,
                "approved_at": agent.approved_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Approve agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể duyệt đại lý"
        )

@router.post("/{agent_id}/reject")
@manager_or_admin()
async def reject_agent(
    agent_id: int,
    reason: str = Query(..., description="Reason for rejection"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reject agent application (change status to REJECTED)
    """
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        if agent.status != AgentStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể từ chối đại lý đang chờ duyệt"
            )
        
        # Update agent status
        agent.status = AgentStatus.REJECTED
        agent.approved_by_id = current_user.id
        agent.approved_at = datetime.utcnow()
        agent.approval_notes = f"Rejected: {reason}"
        agent.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent rejected",
            agent.id,
            f"Agent rejected with reason: {reason}"
        )
        
        # Send rejection email to agent
        user = db.query(User).filter(User.id == agent.user_id).first()
        if user and user.email:
            try:
                EmailUtils.send_email(
                    to_email=user.email,
                    subject="Đăng ký đại lý bị từ chối",
                    body=f"""
                    Xin chào {user.full_name},
                    
                    Rất tiếc, đơn đăng ký đại lý của bạn đã bị từ chối.
                    
                    Lý do: {reason}
                    
                    Nếu bạn có thắc mắc, vui lòng liên hệ bộ phận hỗ trợ.
                    
                    Trân trọng,
                    Đội ngũ 7TY.VN
                    """
                )
            except Exception as email_error:
                logger.error(f"Failed to send rejection email: {email_error}")
        
        logger.info(f"Agent rejected: {agent.agent_code} by {current_user.username}")
        
        return SuccessResponse(
            message="Agent rejected successfully",
            data={
                "agent_id": agent.id,
                "agent_code": agent.agent_code,
                "status": agent.status.value,
                "rejected_by": current_user.username,
                "reason": reason
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Reject agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể từ chối đại lý"
        )

@router.post("/{agent_id}/suspend")
@manager_or_admin()
async def suspend_agent(
    agent_id: int,
    reason: Optional[str] = Query(None, description="Reason for suspension"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Suspend agent (change status to SUSPENDED)
    """
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        if agent.status == AgentStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đại lý đã bị tạm ngưng"
            )
        
        if agent.status == AgentStatus.BLOCKED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Đại lý đã bị khóa, không thể tạm ngưng"
            )
        
        # Update agent status
        previous_status = agent.status.value
        agent.status = AgentStatus.SUSPENDED
        agent.approval_notes = f"Suspended by {current_user.username}. Reason: {reason}"
        agent.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent suspended",
            agent.id,
            f"Agent suspended from {previous_status}. Reason: {reason}"
        )
        
        # Send suspension email to agent
        user = db.query(User).filter(User.id == agent.user_id).first()
        if user and user.email:
            try:
                EmailUtils.send_email(
                    to_email=user.email,
                    subject="Tài khoản đại lý đã bị tạm ngưng",
                    body=f"""
                    Xin chào {user.full_name},
                    
                    Tài khoản đại lý của bạn đã bị tạm ngưng.
                    
                    Thông tin đại lý:
                    - Mã đại lý: {agent.agent_code}
                    - Trạng thái: Tạm ngưng
                    - Lý do: {reason}
                    - Ngày tạm ngưng: {FormatUtils.format_datetime(datetime.utcnow())}
                    
                    Vui lòng liên hệ với quản trị viên để biết thêm chi tiết.
                    
                    Trân trọng,
                    Đội ngũ 7TY.VN
                    """
                )
            except Exception as email_error:
                logger.error(f"Failed to send suspension email: {email_error}")
        
        logger.warning(f"Agent suspended: {agent.agent_code} by {current_user.username}. Reason: {reason}")
        
        return SuccessResponse(
            message="Agent suspended successfully",
            data={
                "agent_id": agent.id,
                "agent_code": agent.agent_code,
                "status": agent.status.value,
                "reason": reason,
                "suspended_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Suspend agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạm ngưng đại lý"
        )

@router.post("/{agent_id}/reactivate")
@manager_or_admin()
async def reactivate_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reactivate agent (change status to ACTIVE)
    """
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        if agent.status != AgentStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể kích hoạt lại đại lý đang tạm ngưng"
            )
        
        # Update agent status
        agent.status = AgentStatus.ACTIVE
        agent.approval_notes = f"Reactivated by {current_user.username}"
        agent.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent reactivated",
            agent.id,
            "Agent reactivated from suspended status"
        )
        
        # Send reactivation email to agent
        user = db.query(User).filter(User.id == agent.user_id).first()
        if user and user.email:
            try:
                EmailUtils.send_email(
                    to_email=user.email,
                    subject="Tài khoản đại lý đã được kích hoạt lại",
                    body=f"""
                    Xin chào {user.full_name},
                    
                    Tài khoản đại lý của bạn đã được kích hoạt lại thành công.
                    
                    Thông tin đại lý:
                    - Mã đại lý: {agent.agent_code}
                    - Trạng thái: Hoạt động
                    - Ngày kích hoạt lại: {FormatUtils.format_datetime(datetime.utcnow())}
                    
                    Bạn có thể tiếp tục sử dụng hệ thống.
                    
                    Trân trọng,
                    Đội ngũ 7TY.VN
                    """
                )
            except Exception as email_error:
                logger.error(f"Failed to send reactivation email: {email_error}")
        
        logger.info(f"Agent reactivated: {agent.agent_code} by {current_user.username}")
        
        return SuccessResponse(
            message="Agent reactivated successfully",
            data={
                "agent_id": agent.id,
                "agent_code": agent.agent_code,
                "status": agent.status.value,
                "reactivated_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Reactivate agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể kích hoạt lại đại lý"
        )

@router.get("/{agent_id}/bills", response_model=PaginatedResponse)
async def get_agent_bills(
    agent_id: int,
    pagination: Dict = Depends(pagination_params),
    status: Optional[BillStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bills assigned to an agent
    """
    try:
        # Check agent exists
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Build query
        query = db.query(Bill).filter(Bill.agent_id == agent_id)
        
        if status:
            query = query.filter(Bill.status == status)
        
        if start_date:
            query = query.filter(Bill.created_at >= start_date)
        
        if end_date:
            query = query.filter(Bill.created_at <= end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        bills = query.order_by(Bill.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        # Calculate summary
        total_amount = db.query(func.sum(Bill.total_amount)).filter(
            Bill.agent_id == agent_id
        ).scalar() or Decimal('0')
        
        total_commission = db.query(func.sum(Bill.agent_commission)).filter(
            Bill.agent_id == agent_id
        ).scalar() or Decimal('0')
        
        return PaginatedResponse(
            page=page,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=bills,
            summary={
                "total_amount": float(total_amount),
                "total_commission": float(total_commission),
                "total_bills": total
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent bills error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách hóa đơn của đại lý"
        )

@router.get("/{agent_id}/customers", response_model=PaginatedResponse)
async def get_agent_customers(
    agent_id: int,
    pagination: Dict = Depends(pagination_params),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get customers managed by an agent
    """
    try:
        # Check agent exists
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Build query
        query = db.query(Customer).filter(Customer.agent_id == agent_id)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.full_name.ilike(search_term),
                    Customer.customer_code.ilike(search_term),
                    Customer.phone.ilike(search_term),
                    Customer.evn_customer_code.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        customers = query.order_by(Customer.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        return PaginatedResponse(
            page=page,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=customers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent customers error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách khách hàng của đại lý"
        )

@router.get("/{agent_id}/transactions", response_model=Dict[str, Any])
async def get_agent_transactions(
    agent_id: int,
    pagination: Dict = Depends(pagination_params),
    transaction_type: Optional[TransactionType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transactions for an agent
    """
    try:
        # Check agent exists
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Build query
        query = db.query(Transaction).filter(Transaction.agent_id == agent_id)
        
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        if start_date:
            query = query.filter(Transaction.created_at >= start_date)
        
        if end_date:
            query = query.filter(Transaction.created_at <= end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        transactions = query.order_by(Transaction.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        # Calculate summary
        total_deposit = db.query(func.sum(Transaction.amount)).filter(
            Transaction.agent_id == agent_id,
            Transaction.transaction_type == TransactionType.DEPOSIT,
            Transaction.status == TransactionStatus.COMPLETED
        ).scalar() or Decimal('0')
        
        total_withdraw = db.query(func.sum(Transaction.amount)).filter(
            Transaction.agent_id == agent_id,
            Transaction.transaction_type == TransactionType.WITHDRAW,
            Transaction.status == TransactionStatus.COMPLETED
        ).scalar() or Decimal('0')
        
        total_commission = db.query(func.sum(Transaction.amount)).filter(
            Transaction.agent_id == agent_id,
            Transaction.transaction_type == TransactionType.COMMISSION,
            Transaction.status == TransactionStatus.COMPLETED
        ).scalar() or Decimal('0')
        
        total_pages = (total + limit - 1) // limit
        
        return {
            "data": [
                {
                    "id": t.id,
                    "transaction_code": t.transaction_code,
                    "transaction_type": t.transaction_type.value if t.transaction_type else None,
                    "amount": float(t.amount),
                    "fee": float(t.fee) if t.fee else 0,
                    "total_amount": float(t.total_amount) if t.total_amount else float(t.amount),
                    "status": t.status.value if t.status else None,
                    "description": t.description,
                    "customer_code": t.transaction_metadata.get("customer_code") if t.transaction_metadata else None,
                    "customer_name": t.transaction_metadata.get("customer_name") if t.transaction_metadata else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in transactions
            ],
            "page": page,
            "limit": limit,
            "total": total,
            "pages": total_pages,
            "items": [
                {
                    "id": t.id,
                    "transaction_code": t.transaction_code,
                    "transaction_type": t.transaction_type.value if t.transaction_type else None,
                    "amount": float(t.amount),
                    "fee": float(t.fee) if t.fee else 0,
                    "total_amount": float(t.total_amount) if t.total_amount else float(t.amount),
                    "status": t.status.value if t.status else None,
                    "description": t.description,
                    "customer_code": t.transaction_metadata.get("customer_code") if t.transaction_metadata else None,
                    "customer_name": t.transaction_metadata.get("customer_name") if t.transaction_metadata else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None
                }
                for t in transactions
            ],
            "summary": {
                "total_deposit": float(total_deposit),
                "total_withdraw": float(total_withdraw),
                "total_commission": float(total_commission)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent transactions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách giao dịch của đại lý"
        )

@router.get("/{agent_id}/commission", response_model=PaginatedResponse)
async def get_agent_commission(
    agent_id: int,
    pagination: Dict = Depends(pagination_params),
    is_paid: Optional[bool] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get commission logs for an agent
    """
    try:
        # Check agent exists
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Build query
        query = db.query(CommissionLog).filter(CommissionLog.agent_id == agent_id)
        
        if is_paid is not None:
            query = query.filter(CommissionLog.is_paid == is_paid)
        
        if start_date:
            query = query.filter(CommissionLog.calculated_at >= start_date)
        
        if end_date:
            query = query.filter(CommissionLog.calculated_at <= end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        page = pagination["page"]
        limit = pagination["limit"]
        commission_logs = query.order_by(CommissionLog.calculated_at.desc()).offset((page - 1) * limit).limit(limit).all()
        
        # Calculate summary
        total_commission = db.query(func.sum(CommissionLog.commission_amount)).filter(
            CommissionLog.agent_id == agent_id
        ).scalar() or Decimal('0')
        
        paid_commission = db.query(func.sum(CommissionLog.commission_amount)).filter(
            CommissionLog.agent_id == agent_id,
            CommissionLog.is_paid == True
        ).scalar() or Decimal('0')
        
        pending_commission = total_commission - paid_commission
        
        return PaginatedResponse(
            page=page,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=commission_logs,
            summary={
                "total_commission": float(total_commission),
                "paid_commission": float(paid_commission),
                "pending_commission": float(pending_commission)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent commission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy thông tin hoa hồng của đại lý"
        )

@router.post("/{agent_id}/withdraw")
async def withdraw_from_agent(
    agent_id: int,
    amount: float,
    description: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Withdraw money from agent balance
    """
    try:
        # Check amount
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền phải lớn hơn 0"
            )
        
        # Get agent
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check agent status
        if agent.status != AgentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ đại lý đang hoạt động mới có thể rút tiền"
            )
        
        # Check balance
        if agent.available_balance < Decimal(str(amount)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số dư không đủ"
            )
        
        # Only admin can withdraw
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ quản trị viên mới được rút tiền từ tài khoản đại lý"
            )
        
        # Generate transaction code
        transaction_code = f"WTH{datetime.now().strftime('%Y%m%d%H%M%S')}{agent_id:06d}"
        
        # Create transaction
        transaction = Transaction(
            transaction_code=transaction_code,
            agent_id=agent_id,
            user_id=current_user.id,
            transaction_type=TransactionType.WITHDRAW,
            amount=Decimal(str(amount)),
            total_amount=Decimal(str(amount)),
            description=description or f"Withdraw from agent {agent.agent_code}",
            status=TransactionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            previous_balance=agent.balance,
            new_balance=agent.balance - Decimal(str(amount))
        )
        
        # Update agent balance
        agent.balance -= Decimal(str(amount))
        agent.total_withdraw += Decimal(str(amount))
        agent.updated_at = datetime.utcnow()
        
        db.add(transaction)
        db.commit()
        
        # Create activity log
        create_agent_activity_log(
            db, current_user.id,
            "Agent withdraw",
            agent.id,
            f"Withdrew {FormatUtils.format_currency(amount)} from agent balance"
        )
        
        logger.info(f"Withdraw from agent {agent.agent_code}: {amount} by {current_user.username}")
        
        return SuccessResponse(
            message="Withdraw successful",
            data={
                "agent_id": agent.id,
                "agent_code": agent.agent_code,
                "amount": amount,
                "previous_balance": float(transaction.previous_balance),
                "new_balance": float(transaction.new_balance),
                "transaction_code": transaction_code
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Withdraw from agent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể rút tiền từ tài khoản đại lý"
        )

@router.post("/import")
@manager_or_admin()
async def import_agents(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import agents from Excel file
    """
    try:
        # Save uploaded file
        upload_dir = Path(settings.UPLOAD_DIR) / "imports"
        result = await FileUtils.save_upload_file(file, upload_dir)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Không thể lưu file")
            )
        
        # Import agents from Excel
        import_result = await ImportUtils.import_agents_from_excel(
            result["file_path"], db, current_user.id
        )
        
        if not import_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=import_result.get("error", "Nhập dữ liệu thất bại")
            )
        
        # Create activity log
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="import",
            action="Imported agents",
            details=f"Imported {import_result['imported']} agents from file: {file.filename}"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Agents imported: {import_result['imported']} agents by {current_user.username}")
        
        return SuccessResponse(
            message=f"Successfully imported {import_result['imported']} agents",
            data=import_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể nhập danh sách đại lý"
        )

@router.post("/export")
@manager_or_admin()
async def export_agents(
    filters: Dict = Depends(agent_filter_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export agents to Excel
    """
    try:
        # Get agents
        query = get_agent_query(db, filters)
        agents = query.options(joinedload(Agent.user)).all()
        
        # Prepare data
        data = []
        for agent in agents:
            data.append({
                "Mã đại lý": agent.agent_code,
                "Họ và tên": agent.user.full_name,
                "Số điện thoại": agent.user.phone,
                "Email": agent.user.email,
                "Tên công ty": agent.company_name,
                "Mã số thuế": agent.tax_code,
                "Loại đại lý": agent.agent_type.value,
                "Trạng thái": agent.status.value,
                "Tỷ lệ hoa hồng (%)": float(agent.commission_rate),
                "Số dư": float(agent.balance),
                "Số dư đóng băng": float(agent.frozen_balance),
                "Tổng doanh số": float(agent.total_sales),
                "Tổng hoa hồng": float(agent.total_commission),
                "Số khách hàng": agent.total_customers,
                "Số hóa đơn": agent.total_bills,
                "Tỷ lệ thành công (%)": float(agent.success_rate),
                "Giới hạn/ngày": float(agent.daily_limit),
                "Giới hạn/giao dịch": float(agent.per_transaction_limit),
                "Ngày tạo": FormatUtils.format_datetime(agent.created_at),
                "Ngày duyệt": FormatUtils.format_datetime(agent.approved_at) if agent.approved_at else "",
                "Người duyệt": agent.approved_by.username if agent.approved_by else ""
            })
        
        # Export to Excel
        file_path = ExportUtils.export_to_excel(data, "agents_export")
        
        # Create activity log
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="export",
            action="Exported agents",
            details=f"Exported {len(agents)} agents to Excel"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Agents exported: {len(agents)} agents by {current_user.username}")
        
        # Build correct download URL
        file_name = Path(file_path).name
        download_url = f"/static/uploads/exports/{file_name}"
        
        return SuccessResponse(
            message=f"Exported {len(agents)} agents successfully",
            data={
                "file_path": file_path,
                "agent_count": len(agents),
                "download_url": download_url
            }
        )
        
    except Exception as e:
        logger.error(f"Export agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xuất danh sách đại lý"
        )

@router.get("/top-performing", response_model=List[AgentStatsResponse])
@manager_or_admin()
async def get_top_performing_agents(
    limit: int = Query(10, ge=1, le=50),
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top performing agents by sales
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)
        
        # Query top agents by sales
        top_agents = db.query(
            Agent.id,
            Agent.agent_code,
            User.full_name,
            func.sum(Bill.total_amount).label("total_sales"),
            func.sum(Bill.agent_commission).label("total_commission"),
            func.count(Bill.id).label("total_bills"),
            func.count(distinct(Customer.id)).label("total_customers")
        ).join(
            User, Agent.user_id == User.id
        ).join(
            Bill, Agent.id == Bill.agent_id
        ).outerjoin(
            Customer, Agent.id == Customer.agent_id
        ).filter(
            Bill.payment_date.between(start_date, end_date),
            Bill.status.in_([BillStatus.SOLD, BillStatus.PAID]),
            User.is_deleted == False
        ).group_by(
            Agent.id, Agent.agent_code, User.full_name
        ).order_by(
            func.sum(Bill.total_amount).desc()
        ).limit(limit).all()
        
        # Prepare response
        result = []
        for agent in top_agents:
            # Calculate success rate
            total_assigned = db.query(func.count(Bill.id)).filter(
                Bill.agent_id == agent.id
            ).scalar() or 0
            
            success_rate = Decimal('0')
            if total_assigned > 0:
                success_rate = (Decimal(agent.total_bills) / Decimal(total_assigned)) * 100
            
            result.append(AgentStatsResponse(
                agent_id=agent.id,
                agent_code=agent.agent_code,
                full_name=agent.full_name,
                total_sales=agent.total_sales or Decimal('0'),
                total_commission=agent.total_commission or Decimal('0'),
                total_bills=agent.total_bills or 0,
                success_rate=success_rate,
                total_customers=agent.total_customers or 0
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Get top performing agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách đại lý xuất sắc"
        )

@router.get("/{agent_id}/report")
async def get_agent_report(
    agent_id: int,
    date_range: DateRange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed report for an agent
    """
    try:
        # Check agent exists
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đại lý"
            )
        
        # Check permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if agent.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập"
                )
        
        # Query bills in date range
        bills = db.query(Bill).filter(
            Bill.agent_id == agent_id,
            Bill.payment_date.between(date_range.start_date, date_range.end_date),
            Bill.status.in_([BillStatus.SOLD, BillStatus.PAID])
        ).all()
        
        # Query transactions
        transactions = db.query(Transaction).filter(
            Transaction.agent_id == agent_id,
            Transaction.created_at.between(date_range.start_date, date_range.end_date),
            Transaction.status == TransactionStatus.COMPLETED
        ).all()
        
        # Calculate statistics
        total_sales = sum(bill.total_amount for bill in bills)
        total_commission = sum(bill.agent_commission for bill in bills)
        total_deposit = sum(
            t.amount for t in transactions 
            if t.transaction_type == TransactionType.DEPOSIT
        )
        total_withdraw = sum(
            t.amount for t in transactions 
            if t.transaction_type == TransactionType.WITHDRAW
        )
        
        # Group by day
        daily_sales = {}
        for bill in bills:
            day = bill.payment_date.date().isoformat()
            if day not in daily_sales:
                daily_sales[day] = {
                    "date": day,
                    "sales": Decimal('0'),
                    "bills": 0,
                    "commission": Decimal('0')
                }
            daily_sales[day]["sales"] += bill.total_amount
            daily_sales[day]["bills"] += 1
            daily_sales[day]["commission"] += bill.agent_commission
        
        daily_sales_list = sorted(daily_sales.values(), key=lambda x: x["date"])
        
        return ReportResponse(
            report_type="agent_performance",
            date_range=date_range,
            total_amount=total_sales,
            total_bills=len(bills),
            total_commission=total_commission,
            items=daily_sales_list,
            summary={
                "total_deposit": float(total_deposit),
                "total_withdraw": float(total_withdraw),
                "net_balance": float(total_deposit - total_withdraw),
                "average_daily_sales": float(total_sales / len(daily_sales)) if daily_sales else 0,
                "average_bill_amount": float(total_sales / len(bills)) if bills else 0
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạo báo cáo đại lý"
        )

# Health check endpoint
@router.get("/health")
async def agents_health():
    """
    Agents service health check
    """
    return {
        "status": "healthy",
        "service": "agents",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "public": ["/{id}"],
            "manager": ["/", "/stats", "/import", "/export", "/top-performing"],
            "admin": ["/{id}/deposit", "{id}/withdraw", "{id}/approve", "{id}/suspend"]
        }
    }

# Helper function for imports (to be added to ImportUtils)
async def import_agents_from_excel(file_path: str, db: Session, created_by_id: int) -> Dict[str, Any]:
    """
    Import agents from Excel file
    """
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Validate required columns
        required_columns = ['username', 'email', 'full_name', 'phone', 'agent_code']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                "success": False,
                "error": f"Missing required columns: {', '.join(missing_columns)}"
            }
        
        imported = 0
        skipped = 0
        errors = []
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Check if user already exists
                existing_user = db.query(User).filter(
                    (User.username == str(row['username'])) | (User.email == str(row['email']))
                ).first()
                
                if existing_user:
                    skipped += 1
                    errors.append(f"Row {index + 2}: User already exists")
                    continue
                
                # Check if agent code exists
                existing_agent = db.query(Agent).filter(
                    Agent.agent_code == str(row['agent_code'])
                ).first()
                
                if existing_agent:
                    skipped += 1
                    errors.append(f"Row {index + 2}: Agent code already exists")
                    continue
                
                # Create user
                user = User(
                    username=str(row['username']),
                    email=str(row['email']),
                    full_name=str(row['full_name']),
                    phone=str(row.get('phone', '')),
                    role="agent",
                    is_active=True
                )
                # Set default password (username + "123")
                user.set_password(f"{row['username']}@123")
                
                db.add(user)
                db.commit()
                db.refresh(user)
                
                # Create agent
                agent = Agent(
                    user_id=user.id,
                    agent_code=str(row['agent_code']),
                    company_name=row.get('company_name'),
                    tax_code=row.get('tax_code'),
                    agent_type=row.get('agent_type', 'individual'),
                    status=row.get('status', 'pending'),
                    commission_rate=Decimal(str(row.get('commission_rate', 0))),
                    min_commission=Decimal(str(row.get('min_commission', 0))),
                    max_commission=Decimal(str(row.get('max_commission', 10000000))),
                    daily_limit=Decimal(str(row.get('daily_limit', 50000000))),
                    per_transaction_limit=Decimal(str(row.get('per_transaction_limit', 10000000)))
                )
                
                db.add(agent)
                db.commit()
                
                imported += 1
                
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
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error importing agents from Excel: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ===== DEPOSIT SYSTEM (Hệ thống nạp tiền) =====

@router.post("/{agent_id}/deposit", response_model=Dict[str, Any])
def agent_deposit(
    agent_id: int,
    deposit_data: DepositRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Nạp tiền cho Đại Lý
    - Chỉ Admin/Manager có thể nạp tiền
    - Kiểm tra giới hạn giao dịch
    - Cập nhật số dư agent
    - Tạo transaction record
    """
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin/Manager mới được nạp tiền cho Đại Lý"
        )
    
    # Get agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Đại Lý"
        )
    
    # Validate amount
    if deposit_data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số tiền phải lớn hơn 0"
        )
    
    # Check per_transaction_limit
    if deposit_data.amount > agent.per_transaction_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số tiền vượt quá giới hạn {FormatUtils.format_currency(agent.per_transaction_limit)}/giao dịch"
        )
    
    # Check daily limit
    today = datetime.utcnow().date()
    today_deposits = db.query(func.sum(Transaction.amount)).filter(
        Transaction.agent_id == agent_id,
        Transaction.transaction_type == TransactionType.DEPOSIT,
        Transaction.status == TransactionStatus.COMPLETED,
        func.date(Transaction.created_at) == today
    ).scalar() or 0
    
    if today_deposits + deposit_data.amount > agent.daily_limit:
        remaining = agent.daily_limit - today_deposits
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vượt quá giới hạn nạp tiền hôm nay. Còn lại: {FormatUtils.format_currency(remaining)}"
        )
    
    try:
        # Save previous balance
        previous_balance = agent.balance
        
        # Create transaction
        transaction = Transaction(
            transaction_code=generate_transaction_code(),
            agent_id=agent_id,
            user_id=current_user.id,
            transaction_type=TransactionType.DEPOSIT,
            amount=deposit_data.amount,
            fee=Decimal(0),
            total_amount=deposit_data.amount,
            status=TransactionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            payment_method=deposit_data.payment_method,
            previous_balance=previous_balance,
            new_balance=previous_balance + deposit_data.amount,
            description=f"Nạp tiền từ {current_user.full_name}",
            notes=deposit_data.notes,
            transaction_metadata={
                "deposited_by": current_user.username,
                "deposited_by_id": current_user.id
            }
        )
        
        # Update agent balance
        agent.balance = previous_balance + deposit_data.amount
        agent.total_deposit = (agent.total_deposit or 0) + deposit_data.amount
        agent.updated_at = datetime.utcnow()
        
        # Save
        db.add(transaction)
        db.add(agent)
        db.flush()
        db.commit()
        db.refresh(transaction)
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.PAYMENT,
            action="agent_deposit",
            resource_type="agent",
            resource_id=agent_id,
            details=f"Nạp {FormatUtils.format_currency(deposit_data.amount)} cho Đại Lý {agent.agent_name} bằng {deposit_data.payment_method}"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Agent {agent_id} received deposit {transaction.transaction_code}: {deposit_data.amount}")
        
        return {
            "success": True,
            "message": "Nạp tiền thành công",
            "data": {
                "transaction_id": transaction.id,
                "transaction_code": transaction.transaction_code,
                "amount": str(deposit_data.amount),
                "previous_balance": str(previous_balance),
                "new_balance": str(agent.balance),
                "payment_method": deposit_data.payment_method,
                "created_at": transaction.created_at.isoformat()
            }
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing deposit for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi xử lý nạp tiền: {str(e)}"
        )


@router.get("/{agent_id}/wallet", response_model=Dict[str, Any])
def get_agent_wallet(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy thông tin ví/tài khoản của Đại Lý
    """
    # Get agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Đại Lý"
        )
    
    # Check permission - agent can only view their own wallet
    if current_user.role == UserRole.AGENT and current_user.id != agent.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không được phép xem ví của Đại Lý khác"
        )
    
    return {
        "success": True,
        "data": {
            "agent_id": agent.id,
            "agent_name": agent.agent_name,
            "agent_code": agent.agent_code,
            "current_balance": str(agent.balance),
            "frozen_balance": str(agent.frozen_balance),
            "available_balance": str(agent.balance - agent.frozen_balance),
            "total_deposit": str(agent.total_deposit),
            "total_withdraw": str(agent.total_withdraw),
            "total_sales": str(agent.total_sales),
            "total_commission": str(agent.total_commission),
            "daily_limit": str(agent.daily_limit),
            "per_transaction_limit": str(agent.per_transaction_limit),
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
        }
    }


@router.get("/{agent_id}/deposit-requests", response_model=Dict[str, Any])
def get_agent_deposit_requests(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách yêu cầu nạp tiền từ Đại Lý
    Trả về dữ liệu giả để demo giao diện
    """
    # Get agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Đại Lý"
        )
    
    # Check permission
    if current_user.role == UserRole.AGENT and current_user.id != agent.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không được phép xem yêu cầu nạp tiền của Đại Lý khác"
        )
    
    # Demo data - replace with real data from database later
    demo_requests = [
        {
            "id": 1,
            "agent_id": agent_id,
            "amount": 5000000,
            "payment_method": "bank_transfer",
            "status": "pending",
            "notes": "Yêu cầu nạp tiền cho hoạt động kinh doanh",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": 2,
            "agent_id": agent_id,
            "amount": 10000000,
            "payment_method": "cash",
            "status": "approved",
            "notes": "Nạp tiền mặt",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "updated_at": (datetime.now() - timedelta(days=1)).isoformat()
        },
        {
            "id": 3,
            "agent_id": agent_id,
            "amount": 7500000,
            "payment_method": "bank_transfer",
            "status": "reconciled",
            "notes": "Đã đối soát",
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "updated_at": (datetime.now() - timedelta(days=2)).isoformat()
        }
    ]
    
    return {
        "data": demo_requests,
        "total": len(demo_requests)
    }


@router.get("/{agent_id}/deposit-history", response_model=Dict[str, Any])
def get_agent_deposit_history(
    agent_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy lịch sử nạp tiền của Đại Lý
    """
    # Get agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy Đại Lý"
        )
    
    # Check permission
    if current_user.role == UserRole.AGENT and current_user.id != agent.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không được phép xem lịch sử nạp tiền của Đại Lý khác"
        )
    
    # Get deposits
    deposits = db.query(Transaction).filter(
        Transaction.agent_id == agent_id,
        Transaction.transaction_type == TransactionType.DEPOSIT
    ).order_by(desc(Transaction.created_at)).offset(skip).limit(limit).all()
    
    total = db.query(func.count(Transaction.id)).filter(
        Transaction.agent_id == agent_id,
        Transaction.transaction_type == TransactionType.DEPOSIT
    ).scalar()
    
    return {
        "success": True,
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "id": d.id,
                "transaction_code": d.transaction_code,
                "amount": str(d.amount),
                "fee": str(d.fee),
                "total_amount": str(d.total_amount),
                "payment_method": d.payment_method,
                "status": d.status.value,
                "notes": d.notes,
                "previous_balance": str(d.previous_balance) if d.previous_balance else None,
                "new_balance": str(d.new_balance) if d.new_balance else None,
                "created_at": d.created_at.isoformat()
            }
            for d in deposits
        ]
    }


# ===== AGENT MOBILE APP DEPOSIT REQUEST =====

@router.post("/{agent_id}/deposit-request", response_model=Dict[str, Any])
async def create_deposit_request(
    agent_id: int,
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a deposit request from agent mobile app
    - Chuyển khoản: Status = pending, waiting for admin approval
    - Nhân viên đến thu: Status = pending, notify assigned staff
    """
    try:
        # Verify agent exists and belongs to current user (if agent)
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Đại Lý"
            )
        
        # Agent can only request for their own account
        if current_user.role == UserRole.AGENT and current_user.id != agent.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không được phép yêu cầu nạp tiền cho Đại Lý khác"
            )
        
        # Validate amount
        amount = request_data.get('amount')
        deposit_type = request_data.get('type', 'transfer')  # transfer or cash
        
        if not amount or amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền phải lớn hơn 0"
            )
        
        amount = Decimal(str(amount))
        
        # Create transaction record for request
        transaction = Transaction(
            transaction_code=generate_transaction_code(),
            agent_id=agent_id,
            user_id=current_user.id,
            transaction_type=TransactionType.DEPOSIT,
            amount=amount,
            fee=Decimal(0),
            total_amount=amount,
            status=TransactionStatus.PENDING,  # Waiting for approval
            payment_method=f"mobile_app_{deposit_type}",
            previous_balance=agent.balance,
            new_balance=agent.balance,  # Won't update until approved
            description=f"Deposit request from mobile app ({deposit_type})",
            notes=f"Deposit type: {deposit_type}",
            transaction_metadata={
                "requested_by": current_user.username,
                "deposit_type": deposit_type,
                "app": "agent_mobile"
            }
        )
        
        db.add(transaction)
        db.flush()
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.PAYMENT,
            action="deposit_request_created",
            resource_type="agent",
            resource_id=agent_id,
            details=f"Agent {agent.agent_code} requested {deposit_type} deposit {FormatUtils.format_currency(amount)} via mobile app"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Deposit request {transaction.transaction_code} created for agent {agent_id}")
        
        # Broadcast real-time notification to admin
        try:
            await ws_manager.broadcast({
                "type": "new_deposit_request",
                "data": {
                    "agent_id": agent_id,
                    "agent_code": agent.agent_code,
                    "agent_name": agent.user.full_name if agent.user else "Unknown",
                    "transaction_id": transaction.id,
                    "transaction_code": transaction.transaction_code,
                    "amount": str(amount),
                    "deposit_type": deposit_type,
                    "created_at": transaction.created_at.isoformat()
                },
                "message": f"🔔 {agent.agent_code} yêu cầu nạp {FormatUtils.format_currency(amount)}"
            })
            logger.info(f"Deposit notification broadcasted successfully")
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast deposit notification: {ws_error}")
        
        return {
            "success": True,
            "message": f"Yêu cầu nạp tiền đã được gửi. Vui lòng chờ xác nhận từ {'Admin' if deposit_type == 'transfer' else 'Nhân Viên'}",
            "data": {
                "transaction_id": transaction.id,
                "transaction_code": transaction.transaction_code,
                "amount": str(amount),
                "type": deposit_type,
                "status": transaction.status.value,
                "created_at": transaction.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating deposit request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi tạo yêu cầu nạp tiền: {str(e)}"
        )


# ===== APPROVE DEPOSIT REQUEST =====

@router.post("/{agent_id}/approve-deposit/{transaction_id}", response_model=Dict[str, Any])
@manager_or_admin()
async def approve_deposit_request(
    agent_id: int,
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve a pending deposit request and add balance to agent
    """
    try:
        # Get agent
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Đại Lý"
            )
        
        # Get transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.agent_id == agent_id,
            Transaction.transaction_type == TransactionType.DEPOSIT,
            Transaction.status == TransactionStatus.PENDING
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy lệnh nạp tiền hoặc đã được xử lý"
            )
        
        # Update transaction status
        transaction.status = TransactionStatus.COMPLETED
        transaction.new_balance = agent.balance + transaction.amount
        transaction.notes = f"Approved by {current_user.username} at {datetime.utcnow().isoformat()}"
        
        # Update agent balance
        previous_balance = agent.balance
        agent.balance += transaction.amount
        agent.total_deposit += transaction.amount
        agent.updated_at = datetime.utcnow()
        
        # Process reward points for deposit
        reward_points = 0
        try:
            from routers.rewards import process_reward_for_deposit
            reward_points = process_reward_for_deposit(db, agent, transaction.amount, transaction.id)
        except Exception as reward_error:
            logger.warning(f"Failed to process deposit reward: {reward_error}")
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.PAYMENT,
            action="deposit_approved",
            resource_type="agent",
            resource_id=agent_id,
            details=f"Approved deposit {transaction.transaction_code}: {FormatUtils.format_currency(transaction.amount)} for {agent.agent_code}. Balance: {FormatUtils.format_currency(previous_balance)} -> {FormatUtils.format_currency(agent.balance)}" + (f" (+{reward_points} điểm thưởng)" if reward_points > 0 else "")
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Deposit {transaction.transaction_code} approved for agent {agent.agent_code} by {current_user.username}" + (f" (+{reward_points} points)" if reward_points > 0 else ""))
        
        # Broadcast real-time notification (deposit approved)
        try:
            await ws_manager.broadcast({
                "type": "deposit_approved",
                "data": {
                    "agent_id": agent_id,
                    "agent_code": agent.agent_code,
                    "transaction_code": transaction.transaction_code,
                    "amount": str(transaction.amount),
                    "new_balance": str(agent.balance),
                    "reward_points": reward_points,
                    "approved_by": current_user.username
                },
                "message": f"✅ Đã duyệt nạp {FormatUtils.format_currency(transaction.amount)} cho {agent.agent_code}" + (f" (+{reward_points} điểm)" if reward_points > 0 else "")
            })
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast approval notification: {ws_error}")
        
        return {
            "success": True,
            "message": f"Đã duyệt nạp {FormatUtils.format_currency(transaction.amount)} cho {agent.agent_code}",
            "data": {
                "transaction_code": transaction.transaction_code,
                "amount": str(transaction.amount),
                "previous_balance": str(previous_balance),
                "new_balance": str(agent.balance),
                "approved_by": current_user.username,
                "approved_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving deposit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi duyệt nạp tiền: {str(e)}"
        )


# ===== REJECT DEPOSIT REQUEST =====

@router.post("/{agent_id}/reject-deposit/{transaction_id}", response_model=Dict[str, Any])
@manager_or_admin()
async def reject_deposit_request(
    agent_id: int,
    transaction_id: int,
    request_data: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reject a pending deposit request
    """
    try:
        # Get agent
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Đại Lý"
            )
        
        # Get transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.agent_id == agent_id,
            Transaction.transaction_type == TransactionType.DEPOSIT,
            Transaction.status == TransactionStatus.PENDING
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy lệnh nạp tiền hoặc đã được xử lý"
            )
        
        # Get rejection reason
        reason = request_data.get('reason', 'Không có lý do') if request_data else 'Không có lý do'
        
        # Update transaction status
        transaction.status = TransactionStatus.CANCELLED
        transaction.notes = f"Rejected by {current_user.username}: {reason}"
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.PAYMENT,
            action="deposit_rejected",
            resource_type="agent",
            resource_id=agent_id,
            details=f"Rejected deposit {transaction.transaction_code}: {FormatUtils.format_currency(transaction.amount)} for {agent.agent_code}. Reason: {reason}"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Deposit {transaction.transaction_code} rejected for agent {agent.agent_code} by {current_user.username}")
        
        # Broadcast real-time notification
        try:
            await ws_manager.broadcast({
                "type": "deposit_rejected",
                "data": {
                    "agent_id": agent_id,
                    "agent_code": agent.agent_code,
                    "transaction_code": transaction.transaction_code,
                    "amount": str(transaction.amount),
                    "reason": reason,
                    "rejected_by": current_user.username
                },
                "message": f"❌ Đã từ chối nạp {FormatUtils.format_currency(transaction.amount)} cho {agent.agent_code}"
            })
        except Exception as ws_error:
            logger.warning(f"Failed to broadcast rejection notification: {ws_error}")
        
        return {
            "success": True,
            "message": f"Đã từ chối yêu cầu nạp tiền",
            "data": {
                "transaction_code": transaction.transaction_code,
                "amount": str(transaction.amount),
                "reason": reason,
                "rejected_by": current_user.username,
                "rejected_at": datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting deposit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi từ chối nạp tiền: {str(e)}"
        )


# ===== GET PENDING DEPOSIT REQUESTS (ADMIN) =====

@router.get("/pending-deposits", response_model=Dict[str, Any])
def get_pending_deposit_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Get all pending deposit requests for admin dashboard
    """
    try:
        # Query pending deposits
        query = db.query(Transaction).filter(
            Transaction.transaction_type == TransactionType.DEPOSIT,
            Transaction.status == TransactionStatus.PENDING,
            Transaction.agent_id.isnot(None)
        ).order_by(desc(Transaction.created_at))
        
        total = query.count()
        deposits = query.offset(skip).limit(limit).all()
        
        # Get agent info for each deposit
        result = []
        for d in deposits:
            agent = db.query(Agent).filter(Agent.id == d.agent_id).first()
            result.append({
                "id": d.id,
                "transaction_code": d.transaction_code,
                "agent_id": d.agent_id,
                "agent_code": agent.agent_code if agent else None,
                "agent_name": agent.full_name if agent else (agent.user.full_name if agent and agent.user else "N/A"),
                "amount": str(d.amount),
                "deposit_type": d.transaction_metadata.get('deposit_type', 'transfer') if d.transaction_metadata else 'transfer',
                "payment_method": d.payment_method,
                "status": d.status.value,
                "description": d.description,
                "created_at": d.created_at.isoformat()
            })
        
        return {
            "success": True,
            "total": total,
            "items": result
        }
        
    except Exception as e:
        logger.error(f"Error getting pending deposits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi lấy danh sách yêu cầu nạp tiền: {str(e)}"
        )


# ===== AGENT BILL PAYMENT (Electricity, etc.) =====

@router.post("/{agent_id}/pay-bill", response_model=Dict[str, Any])
async def agent_pay_bill(
    agent_id: int,
    payment_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Agent pays for a bill (electricity, etc.) - deducts from agent balance
    """
    try:
        # Verify agent exists and belongs to current user
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy Đại Lý"
            )
        
        # Agent can only pay from their own account
        if current_user.role == UserRole.AGENT and current_user.id != agent.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền thực hiện giao dịch"
            )
        
        # Get payment details
        amount = payment_data.get('amount')
        customer_code = payment_data.get('customer_code', '')
        customer_name = payment_data.get('customer_name', '')
        description = payment_data.get('description', 'Thanh toán hóa đơn điện')
        bill_type = payment_data.get('bill_type', 'electricity')
        
        if not amount or amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số tiền phải lớn hơn 0"
            )
        
        amount = Decimal(str(amount))
        
        # Check sufficient balance
        if agent.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số dư không đủ. Số dư hiện tại: {FormatUtils.format_currency(agent.balance)}"
            )
        
        # Store previous balance
        previous_balance = agent.balance
        
        # Deduct from agent balance
        agent.balance -= amount
        agent.updated_at = datetime.utcnow()
        
        # Create transaction record
        transaction = Transaction(
            transaction_code=generate_transaction_code(),
            agent_id=agent_id,
            user_id=current_user.id,
            transaction_type=TransactionType.BILL_PAYMENT,
            amount=amount,
            fee=Decimal(0),
            total_amount=amount,
            status=TransactionStatus.COMPLETED,
            payment_method="agent_wallet",
            previous_balance=previous_balance,
            new_balance=agent.balance,
            description=description,
            notes=f"Customer: {customer_code} - {customer_name}",
            completed_at=datetime.utcnow(),
            transaction_metadata={
                "bill_type": bill_type,
                "customer_code": customer_code,
                "customer_name": customer_name,
                "app": "agent_mobile"
            }
        )
        
        db.add(transaction)
        db.flush()
        
        # Get additional info from payment_data
        customer_address = payment_data.get('customer_address', '')
        period = payment_data.get('period', datetime.now().strftime('%Y-%m'))
        
        # Create Bill record to store in Kho hóa đơn
        bill = Bill(
            bill_code=transaction.transaction_code,  # Use transaction_code as bill_code
            customer_code=customer_code,
            customer_name=customer_name,
            customer_address=customer_address,
            evn_customer_code=customer_code,
            period=period,
            total_amount=amount,
            electricity_amount=amount,
            vat_amount=Decimal(0),
            other_fees=Decimal(0),
            agent_id=agent_id,
            status=BillStatus.IN_STOCK,
            payment_date=datetime.utcnow(),
            created_by_id=current_user.id,
            payment_method="agent_wallet",
            transaction_ref=transaction.transaction_code,
            notes=f"Thanh toán qua App Đại Lý - {agent.agent_code}",
            bill_metadata={
                "bill_type": bill_type,
                "agent_code": agent.agent_code,
                "app": "agent_mobile",
                "transaction_id": transaction.id
            }
        )
        
        db.add(bill)
        db.flush()
        
        logger.info(f"Bill {bill.id} created with code {bill.bill_code} for agent {agent.agent_code}")
        
        # Link transaction to bill
        transaction.bill_id = bill.id
        
        # Update agent stats
        agent.total_sales = (agent.total_sales or Decimal(0)) + amount
        agent.total_successful_bills = (agent.total_successful_bills or 0) + 1
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type=ActivityType.PAYMENT,
            action="bill_payment",
            resource_type="agent",
            resource_id=agent_id,
            details=f"Agent {agent.agent_code} paid bill {customer_code}: {FormatUtils.format_currency(amount)}"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Bill payment {transaction.transaction_code} completed for agent {agent_id}")
        
        return {
            "success": True,
            "message": "Thanh toán thành công",
            "data": {
                "transaction_id": transaction.id,
                "transaction_code": transaction.transaction_code,
                "amount": str(amount),
                "previous_balance": str(previous_balance),
                "new_balance": str(agent.balance),
                "customer_code": customer_code,
                "customer_name": customer_name,
                "completed_at": transaction.completed_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing bill payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi thanh toán: {str(e)}"
        )


