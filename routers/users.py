from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
import uuid
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from database import get_db
from dependencies import (
    get_current_user, get_current_active_user, require_role, 
    require_permission, admin_only_dep, manager_or_admin, 
    pagination_params, search_params, audit_log,
    rate_limit, api_rate_limit
)
from models import User, UserRole, ActivityLog, Agent, AgentStatus
from schemas import (
    UserCreate, UserResponse, UserUpdate, UserRoleUpdate,
    ChangePasswordRequest, AdminResetPasswordRequest, SuccessResponse, ErrorResponse,
    UserFilterParams, UserSearchResult
)
from utils import (
    SecurityUtils, EmailUtils, ValidationUtils,
    CacheUtils, PasswordUtils
)
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Users"])

# Routes
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current logged-in user's information
    """
    try:
        user = db.query(User).filter(
            User.id == current_user.id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
    
    except Exception as e:
        logger.error(f"Get current user info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current user info"
        )

@router.get("/", response_model=Dict[str, Any])
async def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep),  # Sß╗¡a: thay v├¼ decorator
    pagination: Dict = Depends(pagination_params),
    search: str = Query(None, description="Search by username, email, or full name"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    created_from: Optional[datetime] = Query(None, description="Created from date"),
    created_to: Optional[datetime] = Query(None, description="Created to date")
):
    """
    Get all users (admin only)
    """
    try:
        # Build query
        query = db.query(User).filter(User.is_deleted == False)
        
        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.username.ilike(search_term)) |
                (User.email.ilike(search_term)) |
                (User.full_name.ilike(search_term))
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if created_from:
            query = query.filter(User.created_at >= created_from)
        
        if created_to:
            query = query.filter(User.created_at <= created_to)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and sorting
        if pagination["sort_by"]:
            sort_column = getattr(User, pagination["sort_by"], User.created_at)
            if pagination["sort_order"] == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(User.created_at.desc())
        
        # Apply pagination
        users = query.offset(
            (pagination["page"] - 1) * pagination["limit"]
        ).limit(pagination["limit"]).all()
        
        return {
            "success": True,
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_active": user.is_active,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "created_at": user.created_at.isoformat(),
                    "login_attempts": user.login_attempts,
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None
                }
                for user in users
            ],
            "pagination": {
                "page": pagination["page"],
                "limit": pagination["limit"],
                "total": total,
                "pages": (total + pagination["limit"] - 1) // pagination["limit"]
            }
        }
        
    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )

@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user by ID with additional role information
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions: users can view their own profile, admins can view any
        if current_user.id != user_id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this user"
            )
        
        # Check if user is an agent
        from models import Agent, AgentStatus, Customer
        agent = db.query(Agent).filter(Agent.user_id == user_id).first()
        is_agent = agent is not None
        agent_status = agent.status.value if agent else None
        
        # Check if user is a customer (has card linked)
        customer = db.query(Customer).filter(Customer.user_id == user_id).first()
        is_customer = customer is not None
        
        # Check if user is staff
        is_staff = getattr(user, 'is_staff', False)
        
        # Build response
        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "is_active": user.is_active,
            "last_login": user.last_login,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "login_attempts": user.login_attempts,
            "locked_until": user.locked_until,
            "gender": user.gender,
            "date_of_birth": user.date_of_birth,
            "address": user.address,
            "ward": user.ward,
            "district": user.district,
            "city": user.city,
            "notes": user.notes,
            "cccd_front": user.cccd_front,
            "cccd_back": user.cccd_back,
            # Additional role info
            "is_agent": is_agent,
            "agent_status": agent_status,
            "is_customer": is_customer,
            "is_staff": is_staff
        }
        
        return user_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )

@router.post("/", response_model=UserResponse)
@audit_log(action="create_user", resource_type="user")
async def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Create a new user (admin only)
    """
    try:
        # Normalize username - remove leading zeros
        normalized_username = user_data.username.lstrip('0') if user_data.username else user_data.username
        
        # Check if normalized username already exists
        existing_user = db.query(User).filter(
            User.username == normalized_username
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Check if email already exists
        existing_email = db.query(User).filter(
            User.email == user_data.email
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        
        # Validate password strength
        is_valid, errors = ValidationUtils.validate_password(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(errors)
            )
        
        # Create new user with normalized username (without leading zeros)
        user = User(
            username=normalized_username,
            email=user_data.email,
            full_name=user_data.full_name,
            phone=user_data.phone,
            role=user_data.role,
            is_active=user_data.is_active if user_data.is_active is not None else True
        )
        user.set_password(user_data.password)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # If user is agent, create agent profile
        if user.role == UserRole.AGENT:
            agent_code = f"AG{datetime.now().strftime('%Y%m%d')}{user.id:06d}"
            agent = Agent(
                user_id=user.id,
                agent_code=agent_code,
                agent_type="individual",
                status=AgentStatus.PENDING
            )
            db.add(agent)
            db.commit()
        
        # Send welcome email in background
        if user.email:
            background_tasks.add_task(
                EmailUtils.send_welcome_email,
                user
            )
        
        logger.info(f"User created: {user.username} by {current_user.username}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


# ========== REGISTER USER WITH FULL INFO ==========
UPLOAD_DIR = "static/uploads"

@router.post("/register", response_model=Dict[str, Any])
@audit_log(action="register_user", resource_type="user")
async def register_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep),
    # Basic info
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    role: str = Form("customer_card"),
    # Personal info
    gender: str = Form(""),
    date_of_birth: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    district: str = Form(""),
    ward: str = Form(""),
    notes: str = Form(""),
    # CCCD images
    cccd_front: Optional[UploadFile] = File(None),
    cccd_back: Optional[UploadFile] = File(None),
):
    """Register user with full personal info and CCCD images"""
    try:
        # Validate phone (username)
        if not username or len(username) < 10:
            raise HTTPException(
                status_code=400,
                detail="Phone number must be at least 10 digits"
            )
        
        # Check existing user
        existing = db.query(User).filter(
            User.username == username,
            User.is_deleted == False
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Phone number already registered"
            )
        
        # Map role string to UserRole
        role_map = {
            "admin": UserRole.ADMIN,
            "manager": UserRole.MANAGER,
            "staff": UserRole.STAFF,
            "agent": UserRole.AGENT,
            "viewer": UserRole.VIEWER,
            "customer_card": UserRole.VIEWER  # Map customer_card to VIEWER
        }
        user_role = role_map.get(role.lower(), UserRole.VIEWER)
        
        # Create user
        new_user = User(
            username=username,
            password_hash=SecurityUtils.get_password_hash(password),
            full_name=full_name or username,
            email=email if email else None,
            phone=phone if phone else username,
            role=user_role,
            is_active=True
        )
        
        # Set optional fields if columns exist
        if hasattr(new_user, 'gender'):
            new_user.gender = gender if gender else None
        if hasattr(new_user, 'date_of_birth') and date_of_birth:
            try:
                from datetime import datetime as dt
                new_user.date_of_birth = dt.strptime(date_of_birth, "%Y-%m-%d").date()
            except:
                pass
        if hasattr(new_user, 'address'):
            new_user.address = address if address else None
        if hasattr(new_user, 'city'):
            new_user.city = city if city else None
        if hasattr(new_user, 'district'):
            new_user.district = district if district else None
        if hasattr(new_user, 'ward'):
            new_user.ward = ward if ward else None
        if hasattr(new_user, 'notes'):
            new_user.notes = notes if notes else None
        
        db.add(new_user)
        db.flush()  # Get user ID
        
        # Save CCCD images
        cccd_dir = os.path.join(UPLOAD_DIR, "cccd", str(new_user.id))
        os.makedirs(cccd_dir, exist_ok=True)
        
        if cccd_front and cccd_front.filename:
            ext = os.path.splitext(cccd_front.filename)[1]
            front_path = os.path.join(cccd_dir, f"front{ext}")
            with open(front_path, "wb") as f:
                shutil.copyfileobj(cccd_front.file, f)
            if hasattr(new_user, 'cccd_front'):
                new_user.cccd_front = front_path
        
        if cccd_back and cccd_back.filename:
            ext = os.path.splitext(cccd_back.filename)[1]
            back_path = os.path.join(cccd_dir, f"back{ext}")
            with open(back_path, "wb") as f:
                shutil.copyfileobj(cccd_back.file, f)
            if hasattr(new_user, 'cccd_back'):
                new_user.cccd_back = back_path
        
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"User registered: {new_user.username} by {current_user.username}")
        
        return {
            "success": True,
            "message": "User registered successfully",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "full_name": new_user.full_name,
                "role": new_user.role.value if hasattr(new_user.role, 'value') else str(new_user.role)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Register user error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register user: {str(e)}"
        )


@router.put("/{user_id}", response_model=UserResponse)
@audit_log(action="update_user", resource_type="user")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user information
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions: users can update their own profile, admins/managers can update any
        if current_user.id != user_id and current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this user"
            )
        
        # Prevent non-admins/managers from updating role or active status
        if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            if user_data.role is not None and user_data.role != user.role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators can change user roles"
                )
            
            if user_data.is_active is not None and user_data.is_active != user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only administrators can change user active status"
                )
        
        # Update fields
        update_data = user_data.dict(exclude_unset=True)
        
        # Remove password from update data if present
        update_data.pop("password", None)
        
        for field, value in update_data.items():
            if value is not None:
                setattr(user, field, value)
        
        # Handle special cases
        if user_data.password:
            is_valid, errors = ValidationUtils.validate_password(user_data.password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=" ".join(errors)
                )
            user.set_password(user_data.password)
        
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"User updated: {user.username} by {current_user.username}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.patch("/{user_id}/role", response_model=UserResponse)
@audit_log(action="update_user_role", resource_type="user")
async def update_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Update user role (admin only)
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent changing own role
        if current_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own role"
            )
        
        # Prevent demoting the last admin
        if user.role == UserRole.ADMIN and role_data.role != UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True,
                User.is_deleted == False
            ).count()
            
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the last administrator"
                )
        
        user.role = role_data.role
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"User role updated: {user.username} -> {role_data.role.value} by {current_user.username}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user role error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )

@router.post("/{user_id}/toggle-staff")
async def toggle_staff_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin)
):
    """
    Toggle user's staff status (Nhân viên)
    One user can have multiple roles: Agent + Staff + Customer
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Toggle staff status
        current_status = getattr(user, 'is_staff', False)
        user.is_staff = not current_status
        user.updated_at = datetime.utcnow()
        db.commit()
        
        action = "enabled" if user.is_staff else "disabled"
        logger.info(f"User staff status {action}: {user.username} by {current_user.username}")
        
        return {
            "success": True,
            "message": f"Đã {'bật' if user.is_staff else 'tắt'} quyền Nhân viên cho {user.full_name}",
            "is_staff": user.is_staff
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle staff status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle staff status"
        )

@router.patch("/{user_id}/activate", response_model=UserResponse)
@audit_log(action="activate_user", resource_type="user")
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Activate user account
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already active"
            )
        
        user.is_active = True
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"User activated: {user.username} by {current_user.username}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activate user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user"
        )

@router.patch("/{user_id}/deactivate", response_model=UserResponse)
@audit_log(action="deactivate_user", resource_type="user")
async def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Deactivate user account
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already inactive"
            )
        
        # Prevent deactivating own account
        if current_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account"
            )
        
        # Prevent deactivating the last admin
        if user.role == UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True,
                User.is_deleted == False
            ).count()
            
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last administrator"
                )
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"User deactivated: {user.username} by {current_user.username}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )

@router.patch("/{user_id}/unlock", response_model=UserResponse)
async def unlock_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Unlock user account (reset failed login attempts)
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.login_attempts = 0
        user.locked_until = None
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"User unlocked: {user.username} by {current_user.username}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlock user"
        )

@router.delete("/{user_id}", response_model=SuccessResponse)
@audit_log(action="delete_user", resource_type="user")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Soft delete user (admin only)
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent deleting own account
        if current_user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account"
            )
        
        # Prevent deleting the last admin
        if user.role == UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_deleted == False
            ).count()
            
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last administrator"
                )
        
        # Soft delete
        user.is_active = False
        user.is_deleted = True
        user.deleted_at = datetime.utcnow()
        user.deleted_by = current_user.id
        db.commit()
        
        logger.info(f"User deleted: {user.username} by {current_user.username}")
        
        return SuccessResponse(message="User deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@router.post("/{user_id}/reset-password", response_model=SuccessResponse)
async def reset_user_password(
    user_id: int,
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reset user password (user can reset own, admin can reset any)
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions
        if current_user.id != user_id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to reset this user's password"
            )
        
        # If current user is not admin, verify old password
        if current_user.id == user_id:
            if not user.verify_password(password_data.old_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
        
        # Validate new password
        is_valid, errors = ValidationUtils.validate_password(password_data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(errors)
            )
        
        # Set new password and reset login attempts
        user.set_password(password_data.new_password)
        user.login_attempts = 0
        user.locked_until = None
        user.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Password reset for user: {user.username} by {current_user.username}")
        
        return SuccessResponse(message="Password reset successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.post("/{user_id}/admin-reset-password", response_model=SuccessResponse)
async def admin_reset_user_password(
    user_id: int,
    password_data: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Admin reset user password (no old password required)
    """
    try:
        # Only admin can use this endpoint
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin can reset user password without old password"
            )
        
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Validate new password
        is_valid, errors = ValidationUtils.validate_password(password_data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(errors)
            )
        
        # Set new password and reset login attempts
        user.set_password(password_data.new_password)
        user.login_attempts = 0
        user.locked_until = None
        user.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Admin password reset for user: {user.username} by {current_user.username}")
        
        return SuccessResponse(message="Password reset successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin reset password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.post("/{user_id}/cccd", response_model=SuccessResponse)
async def upload_cccd(
    user_id: int,
    cccd_front: Optional[UploadFile] = File(None),
    cccd_back: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload CCCD/CMND images for user
    """
    try:
        # Check at least one file
        if not cccd_front and not cccd_back:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng chọn ít nhất một ảnh CCCD"
            )
        
        # Get user
        user = db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions (user can update own, admin can update any)
        if current_user.id != user_id and current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this user's CCCD"
            )
        
        # Upload directory
        upload_dir = os.path.join("static", "uploads", "cccd")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Process front image
        if cccd_front:
            # Validate file type
            if not cccd_front.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CCCD front must be an image file"
                )
            
            # Generate unique filename
            ext = cccd_front.filename.split(".")[-1] if "." in cccd_front.filename else "jpg"
            filename_front = f"{user_id}_front_{uuid.uuid4().hex[:8]}.{ext}"
            filepath_front = os.path.join(upload_dir, filename_front)
            
            # Save file
            with open(filepath_front, "wb") as buffer:
                content = await cccd_front.read()
                buffer.write(content)
            
            # Update user record
            user.cccd_front = f"/static/uploads/cccd/{filename_front}"
        
        # Process back image
        if cccd_back:
            # Validate file type
            if not cccd_back.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CCCD back must be an image file"
                )
            
            # Generate unique filename
            ext = cccd_back.filename.split(".")[-1] if "." in cccd_back.filename else "jpg"
            filename_back = f"{user_id}_back_{uuid.uuid4().hex[:8]}.{ext}"
            filepath_back = os.path.join(upload_dir, filename_back)
            
            # Save file
            with open(filepath_back, "wb") as buffer:
                content = await cccd_back.read()
                buffer.write(content)
            
            # Update user record
            user.cccd_back = f"/static/uploads/cccd/{filename_back}"
        
        user.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"CCCD uploaded for user {user.username} by {current_user.username}")
        
        return SuccessResponse(message="Đã upload ảnh CCCD thành công")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload CCCD error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload CCCD"
        )

@router.get("/{user_id}/activities")
async def get_user_activities(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get user activity logs
    """
    try:
        # Check permissions
        if current_user.id != user_id and current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this user's activities"
            )
        
        # Query activities
        query = db.query(ActivityLog).filter(ActivityLog.user_id == user_id)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        activities = query.order_by(
            ActivityLog.created_at.desc()
        ).offset((page - 1) * limit).limit(limit).all()
        
        return {
            "success": True,
            "activities": [
                {
                    "id": activity.id,
                    "action": activity.action,
                    "activity_type": activity.activity_type.value,
                    "ip_address": activity.ip_address,
                    "user_agent": activity.user_agent,
                    "created_at": activity.created_at.isoformat(),
                    "details": activity.details,
                    "resource_type": activity.resource_type,
                    "resource_id": activity.resource_id
                }
                for activity in activities
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user activities error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user activities"
        )

@router.post("/{user_id}/impersonate", response_model=Dict[str, Any])
async def impersonate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Generate impersonation token (admin only)
    """
    try:
        if not settings.ALLOW_IMPERSONATION:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Impersonation is not allowed"
            )
        
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create impersonation token
        from utils import JWTUtils
        access_token = JWTUtils.create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "email": user.email,
                "impersonated_by": current_user.id,
                "is_impersonation": True
            },
            expires_delta=timedelta(minutes=30)  # Short-lived token for security
        )
        
        # Log impersonation activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="security",
            action="user_impersonation",
            details=f"Impersonated user {user.username} ({user.id})",
            ip_address=None,  # Will be filled by request context
            resource_type="user",
            resource_id=user.id
        )
        db.add(activity)
        db.commit()
        
        logger.warning(f"User impersonation: {current_user.username} impersonated {user.username}")
        
        return {
            "success": True,
            "message": "Impersonation token generated",
            "token": access_token,
            "token_type": "bearer",
            "expires_in": 1800,  # 30 minutes in seconds
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value
            },
            "impersonated_by": {
                "id": current_user.id,
                "username": current_user.username
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Impersonation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate impersonation token"
        )

@router.get("/stats/summary")
async def get_users_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_admin)  # Sß╗¡a: thay v├¼ decorator
):
    """
    Get users statistics summary
    """
    try:
        # Total users
        total_users = db.query(User).filter(
            User.is_deleted == False
        ).count()
        
        # Active users
        active_users = db.query(User).filter(
            User.is_active == True,
            User.is_deleted == False
        ).count()
        
        # Users by role
        users_by_role = db.query(
            User.role,
            func.count(User.id).label('count')
        ).filter(
            User.is_deleted == False
        ).group_by(User.role).all()
        
        # New users this month
        start_of_month = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        new_users_this_month = db.query(User).filter(
            User.created_at >= start_of_month,
            User.is_deleted == False
        ).count()
        
        # Locked accounts
        locked_accounts = db.query(User).filter(
            User.locked_until.isnot(None),
            User.locked_until > datetime.utcnow(),
            User.is_deleted == False
        ).count()
        
        # Last 7 days activity
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        active_last_7_days = db.query(User).filter(
            User.last_login >= seven_days_ago,
            User.is_deleted == False
        ).count()
        
        return {
            "success": True,
            "stats": {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "new_users_this_month": new_users_this_month,
                "locked_accounts": locked_accounts,
                "active_last_7_days": active_last_7_days,
                "users_by_role": {
                    role.value: count for role, count in users_by_role
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Get users stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users statistics"
        )

@router.get("/export/csv")
async def export_users_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only_dep),  # Sß╗¡a: thay v├¼ decorator
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    """
    Export users to CSV (admin only)
    """
    try:
        query = db.query(User).filter(User.is_deleted == False)
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        users = query.order_by(User.created_at.desc()).all()
        
        # Create CSV content
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'Username', 'Email', 'Full Name', 'Role',
            'Phone', 'Is Active', 'Last Login', 'Created At',
            'Login Attempts', 'Locked Until'
        ])
        
        # Write data
        for user in users:
            writer.writerow([
                user.id,
                user.username,
                user.email,
                user.full_name or '',
                user.role.value,
                user.phone or '',
                'Yes' if user.is_active else 'No',
                user.last_login.isoformat() if user.last_login else '',
                user.created_at.isoformat(),
                user.login_attempts,
                user.locked_until.isoformat() if user.locked_until else ''
            ])
        
        # Log export activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="export",
            action="export_users_csv",
            details=f"Exported {len(users)} users to CSV"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Users exported to CSV by {current_user.username}")
        
        # Return CSV file
        from fastapi.responses import StreamingResponse
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
        
    except Exception as e:
        logger.error(f"Export users CSV error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export users"
        )

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's profile
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update current user's profile
    """
    try:
        # Prevent updating role or active status
        if user_data.role is not None and user_data.role != current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change your own role"
            )
        
        if user_data.is_active is not None and user_data.is_active != current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot change your own active status"
            )
        
        # Update fields
        update_data = user_data.dict(exclude_unset=True)
        
        # Remove role and is_active from update data
        update_data.pop("role", None)
        update_data.pop("is_active", None)
        
        for field, value in update_data.items():
            if value is not None:
                setattr(current_user, field, value)
        
        current_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"User updated their profile: {current_user.username}")
        
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.post("/me/change-password", response_model=SuccessResponse)
async def change_my_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Change current user's password
    """
    try:
        # Verify current password
        if not current_user.verify_password(password_data.old_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password
        is_valid, errors = ValidationUtils.validate_password(password_data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(errors)
            )
        
        # Set new password
        current_user.set_password(password_data.new_password)
        current_user.login_attempts = 0
        current_user.locked_until = None
        db.commit()
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            activity_type="security",
            action="password_changed",
            details="User changed their password"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"User changed password: {current_user.username}")
        
        return SuccessResponse(message="Password changed successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )

@router.get("/search/quick")
async def quick_search_users(
    query: str = Query(..., min_length=2, description="Search query"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Quick search for users
    """
    try:
        search_term = f"%{query}%"
        
        users = db.query(User).filter(
            User.is_deleted == False,
            (
                (User.username.ilike(search_term)) |
                (User.email.ilike(search_term)) |
                (User.full_name.ilike(search_term))
            )
        ).limit(limit).all()
        
        return {
            "success": True,
            "query": query,
            "results": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_active": user.is_active
                }
                for user in users
            ],
            "total": len(users)
        }
        
    except Exception as e:
        logger.error(f"Quick search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search users"
        )

# Health check endpoint
@router.get("/health")
async def users_health():
    """
    Users service health check
    """
    return {
        "status": "healthy",
        "service": "users",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "user_management": True,
            "role_management": True,
            "profile_management": True,
            "activity_logging": True,
            "export": True
        }
    }


