"""
Staff Management Router - Quản lý Nhân viên
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc, or_
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field
import logging

from database import get_db
from dependencies import get_current_user, get_current_active_admin
from models import (
    User, UserRole, Agent, AgentStatus,
    Staff, StaffStatus, StaffRole
)
from security import get_password_hash

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Staff Management"])


# =========================================
# PYDANTIC SCHEMAS
# =========================================

class StaffBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    staff_role: StaffRole = StaffRole.STAFF
    agent_id: Optional[int] = None  # NULL = nhân viên hệ thống
    notes: Optional[str] = None


class StaffCreate(StaffBase):
    password: str = Field(..., min_length=6)
    username: Optional[str] = None  # Auto-generate từ phone nếu không có


class StaffLink(BaseModel):
    """Schema để liên kết user có sẵn thành nhân viên"""
    user_id: int = Field(..., description="ID của tài khoản cần liên kết")
    department: Optional[str] = None
    position: Optional[str] = None
    staff_role: StaffRole = StaffRole.STAFF
    agent_id: Optional[int] = None  # NULL = nhân viên hệ thống
    notes: Optional[str] = None
    profile_images: Optional[List[str]] = None  # Base64 encoded images


class StaffUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    staff_role: Optional[StaffRole] = None
    status: Optional[StaffStatus] = None
    base_salary: Optional[float] = None
    commission_rate: Optional[float] = None
    notes: Optional[str] = None


class StaffResponse(BaseModel):
    id: int
    staff_code: str
    user_id: int
    full_name: str
    phone: Optional[str]
    email: Optional[str]
    department: Optional[str]
    position: Optional[str]
    staff_role: str
    status: str
    agent_id: Optional[int]
    agent_code: Optional[str] = None
    agent_name: Optional[str] = None
    base_salary: float = 0
    commission_rate: float = 0
    total_commission: float = 0
    total_bills_processed: int = 0
    total_customers_served: int = 0
    total_transactions: int = 0
    joined_date: Optional[str] = None
    created_at: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# =========================================
# HELPER FUNCTIONS
# =========================================

def generate_staff_code(db: Session) -> str:
    """Generate unique staff code: NV000001"""
    last_staff = db.query(Staff).order_by(desc(Staff.id)).first()
    if last_staff:
        # Extract number from code
        try:
            num = int(last_staff.staff_code.replace("NV", ""))
            new_num = num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    return f"NV{new_num:06d}"


def staff_to_response(staff: Staff) -> dict:
    """Convert Staff model to response dict"""
    user = staff.user
    agent = staff.agent
    
    return {
        "id": staff.id,
        "staff_code": staff.staff_code,
        "user_id": staff.user_id,
        "full_name": user.full_name if user else "",
        "phone": user.phone if user else None,
        "email": user.email if user else None,
        "department": staff.department,
        "position": staff.position,
        "staff_role": staff.staff_role.value if staff.staff_role else "STAFF",
        "status": staff.status.value if staff.status else "PENDING",
        "agent_id": staff.agent_id,
        "agent_code": agent.agent_code if agent else None,
        "agent_name": agent.agent_name if agent else None,
        "base_salary": float(staff.base_salary) if staff.base_salary else 0,
        "commission_rate": float(staff.commission_rate) if staff.commission_rate else 0,
        "total_commission": float(staff.total_commission) if staff.total_commission else 0,
        "total_bills_processed": staff.total_bills_processed or 0,
        "total_customers_served": staff.total_customers_served or 0,
        "total_transactions": staff.total_transactions or 0,
        "joined_date": staff.joined_date.isoformat() if staff.joined_date else None,
        "created_at": staff.created_at.isoformat() if staff.created_at else "",
        "notes": staff.notes
    }


# =========================================
# API ENDPOINTS
# =========================================

@router.get("")
async def list_staff(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[StaffStatus] = None,
    staff_role: Optional[StaffRole] = None,
    agent_id: Optional[int] = None,
    system_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Danh sách nhân viên - Admin only"""
    query = db.query(Staff).options(
        joinedload(Staff.user),
        joinedload(Staff.agent)
    )
    
    # Filters
    if search:
        search_term = f"%{search}%"
        query = query.join(User, Staff.user_id == User.id).filter(
            or_(
                User.full_name.ilike(search_term),
                User.phone.ilike(search_term),
                Staff.staff_code.ilike(search_term),
                Staff.department.ilike(search_term)
            )
        )
    
    if status:
        query = query.filter(Staff.status == status)
    
    if staff_role:
        query = query.filter(Staff.staff_role == staff_role)
    
    if agent_id:
        query = query.filter(Staff.agent_id == agent_id)
    
    if system_only:
        query = query.filter(Staff.agent_id == None)
    
    # Count
    total = query.count()
    
    # Paginate
    offset = (page - 1) * limit
    staffs = query.order_by(desc(Staff.created_at)).offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "data": [staff_to_response(s) for s in staffs],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }


@router.get("/stats")
async def get_staff_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Thống kê nhân viên"""
    total = db.query(func.count(Staff.id)).scalar() or 0
    active = db.query(func.count(Staff.id)).filter(Staff.status == StaffStatus.ACTIVE).scalar() or 0
    pending = db.query(func.count(Staff.id)).filter(Staff.status == StaffStatus.PENDING).scalar() or 0
    system_staff = db.query(func.count(Staff.id)).filter(Staff.agent_id == None).scalar() or 0
    agent_staff = db.query(func.count(Staff.id)).filter(Staff.agent_id != None).scalar() or 0
    
    return {
        "success": True,
        "data": {
            "total": total,
            "active": active,
            "pending": pending,
            "inactive": total - active - pending,
            "system_staff": system_staff,
            "agent_staff": agent_staff
        }
    }


@router.get("/{staff_id}")
async def get_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Chi tiết nhân viên"""
    staff = db.query(Staff).options(
        joinedload(Staff.user),
        joinedload(Staff.agent)
    ).filter(Staff.id == staff_id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    
    return {
        "success": True,
        "data": staff_to_response(staff)
    }


@router.post("/link")
async def link_user_to_staff(
    data: StaffLink,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Liên kết tài khoản có sẵn thành nhân viên"""
    # Check user exists
    user = db.query(User).filter(User.id == data.user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    
    # Check if user is already staff
    existing_staff = db.query(Staff).filter(Staff.user_id == data.user_id).first()
    if existing_staff:
        raise HTTPException(
            status_code=400, 
            detail=f"Tài khoản này đã là nhân viên với mã {existing_staff.staff_code}"
        )
    
    # Check agent exists if specified
    if data.agent_id:
        agent = db.query(Agent).filter(Agent.id == data.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Không tìm thấy đại lý")
    
    try:
        # Generate staff code
        staff_code = generate_staff_code(db)
        
        # Update user role to staff
        user.role = UserRole.STAFF
        user.is_staff = True
        
        # Create staff record
        staff = Staff(
            user_id=user.id,
            staff_code=staff_code,
            agent_id=data.agent_id,
            department=data.department,
            position=data.position,
            staff_role=data.staff_role,
            status=StaffStatus.ACTIVE,
            joined_date=date.today(),
            approved_by_id=current_user.id,
            approved_at=datetime.utcnow(),
            notes=data.notes
        )
        
        # Handle profile images if provided
        if data.profile_images:
            # Store profile images as JSON array in notes or a separate field
            import json
            if staff.notes:
                staff.notes = staff.notes + f"\n[Profile Images: {len(data.profile_images)} files]"
            # Note: If you have a profile_images field in Staff model, use it instead
        
        db.add(staff)
        db.commit()
        db.refresh(staff)
        
        logger.info(f"Staff linked: {staff_code} (user_id={user.id}) by admin {current_user.username}")
        
        return {
            "success": True,
            "message": f"Liên kết nhân viên {staff_code} thành công",
            "data": staff_to_response(staff)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error linking staff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_staff(
    data: StaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Tạo nhân viên mới"""
    # Check phone exists
    existing_user = db.query(User).filter(User.phone == data.phone).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Số điện thoại đã được sử dụng")
    
    # Check agent exists if specified
    if data.agent_id:
        agent = db.query(Agent).filter(Agent.id == data.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Không tìm thấy đại lý")
    
    try:
        # Generate staff code
        staff_code = generate_staff_code(db)
        
        # Create user account
        username = data.username or data.phone
        user = User(
            username=username,
            phone=data.phone,
            email=data.email,
            full_name=data.full_name,
            password_hash=get_password_hash(data.password),
            role=UserRole.STAFF,
            is_staff=True,
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Create staff record
        staff = Staff(
            user_id=user.id,
            staff_code=staff_code,
            agent_id=data.agent_id,
            department=data.department,
            position=data.position,
            staff_role=data.staff_role,
            status=StaffStatus.ACTIVE,
            joined_date=date.today(),
            approved_by_id=current_user.id,
            approved_at=datetime.utcnow(),
            notes=data.notes
        )
        db.add(staff)
        db.commit()
        db.refresh(staff)
        
        logger.info(f"Staff created: {staff_code} by admin {current_user.username}")
        
        return {
            "success": True,
            "message": f"Tạo nhân viên {staff_code} thành công",
            "data": staff_to_response(staff)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating staff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{staff_id}")
async def update_staff(
    staff_id: int,
    data: StaffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Cập nhật thông tin nhân viên"""
    staff = db.query(Staff).options(
        joinedload(Staff.user)
    ).filter(Staff.id == staff_id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    
    try:
        # Update user info
        user = staff.user
        if data.full_name:
            user.full_name = data.full_name
        if data.phone:
            user.phone = data.phone
        if data.email:
            user.email = data.email
        
        # Update staff info
        if data.department is not None:
            staff.department = data.department
        if data.position is not None:
            staff.position = data.position
        if data.staff_role is not None:
            staff.staff_role = data.staff_role
        if data.status is not None:
            staff.status = data.status
        if data.base_salary is not None:
            staff.base_salary = Decimal(str(data.base_salary))
        if data.commission_rate is not None:
            staff.commission_rate = Decimal(str(data.commission_rate))
        if data.notes is not None:
            staff.notes = data.notes
        
        db.commit()
        db.refresh(staff)
        
        return {
            "success": True,
            "message": "Cập nhật thành công",
            "data": staff_to_response(staff)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating staff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{staff_id}")
async def delete_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Xóa nhân viên"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    
    try:
        # Soft delete - just mark as inactive
        staff.status = StaffStatus.INACTIVE
        staff.left_date = date.today()
        
        # Also deactivate user account
        user = db.query(User).filter(User.id == staff.user_id).first()
        if user:
            user.is_active = False
            user.is_deleted = True
        
        db.commit()
        
        return {
            "success": True,
            "message": "Đã xóa nhân viên"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting staff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{staff_id}/activate")
async def activate_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Kích hoạt nhân viên"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    
    staff.status = StaffStatus.ACTIVE
    staff.approved_by_id = current_user.id
    staff.approved_at = datetime.utcnow()
    
    # Activate user account
    user = db.query(User).filter(User.id == staff.user_id).first()
    if user:
        user.is_active = True
    
    db.commit()
    
    return {
        "success": True,
        "message": "Đã kích hoạt nhân viên"
    }


@router.post("/{staff_id}/suspend")
async def suspend_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """Tạm ngưng nhân viên"""
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    
    staff.status = StaffStatus.SUSPENDED
    
    db.commit()
    
    return {
        "success": True,
        "message": "Đã tạm ngưng nhân viên"
    }


# =========================================
# STAFF APP ENDPOINTS (cho nhân viên đăng nhập)
# =========================================

@router.get("/me/profile")
async def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy thông tin profile của nhân viên đang đăng nhập"""
    staff = db.query(Staff).options(
        joinedload(Staff.user),
        joinedload(Staff.agent)
    ).filter(Staff.user_id == current_user.id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin nhân viên")
    
    return {
        "success": True,
        "data": staff_to_response(staff)
    }


@router.get("/me/dashboard")
async def get_staff_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dashboard cho nhân viên"""
    staff = db.query(Staff).filter(Staff.user_id == current_user.id).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin nhân viên")
    
    return {
        "success": True,
        "data": {
            "staff_code": staff.staff_code,
            "status": staff.status.value,
            "total_bills_processed": staff.total_bills_processed or 0,
            "total_customers_served": staff.total_customers_served or 0,
            "total_transactions": staff.total_transactions or 0,
            "total_commission": float(staff.total_commission) if staff.total_commission else 0,
            "agent_id": staff.agent_id,
            "agent_name": staff.agent.agent_name if staff.agent else "Hệ thống"
        }
    }


# =========================================
# AGENT'S STAFF ENDPOINTS (cho đại lý quản lý nhân viên của mình)
# =========================================

@router.get("/agent/my-staff")
async def get_agent_staff(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Đại lý xem danh sách nhân viên của mình"""
    # Get agent
    agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Bạn không phải là đại lý")
    
    query = db.query(Staff).options(
        joinedload(Staff.user)
    ).filter(Staff.agent_id == agent.id)
    
    total = query.count()
    offset = (page - 1) * limit
    staffs = query.order_by(desc(Staff.created_at)).offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "data": [staff_to_response(s) for s in staffs],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }
