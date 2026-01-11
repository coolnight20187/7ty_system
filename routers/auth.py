# routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from config import settings
from database import get_db
from dependencies import get_current_user, rate_limit, login_rate_limit
from models import User, UserRole, ActivityLog, Agent, AgentStatus
from schemas import (
    LoginRequest, Token, UserCreate, UserResponse,
    ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest,
    RefreshTokenRequest, SuccessResponse, ErrorResponse
)
from utils import (
    SecurityUtils, JWTUtils, EmailUtils, ValidationUtils,
    CacheUtils, BackgroundTaskUtils
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Authentication"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Cache for login attempts
LOGIN_ATTEMPTS_CACHE_KEY = "login_attempts:{ip}"

# Helper functions
def create_tokens(user: User) -> Dict[str, Any]:
    """Create access and refresh tokens for user"""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = JWTUtils.create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "email": user.email
        },
        expires_delta=access_token_expires
    )
    
    refresh_token = JWTUtils.create_refresh_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "type": "refresh"
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

def log_activity(db: Session, user_id: int, action: str, ip_address: str = None, details: str = None):
    """Log user activity"""
    activity = ActivityLog(
        user_id=user_id,
        activity_type="login" if "login" in action.lower() else "logout",
        action=action,
        ip_address=ip_address,
        details=details
    )
    db.add(activity)
    db.commit()

def handle_failed_login(db: Session, user: User, ip_address: str):
    """Handle failed login attempt"""
    user.login_attempts += 1
    
    # Lock account after 5 failed attempts for 30 minutes
    if user.login_attempts >= 5:
        user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        logger.warning(f"Account {user.username} locked due to too many failed login attempts from {ip_address}")
    
    db.commit()
    
    # Cache login attempts by IP
    cache_key = LOGIN_ATTEMPTS_CACHE_KEY.format(ip=ip_address)
    attempts = CacheUtils.get(cache_key) or 0
    CacheUtils.set(cache_key, attempts + 1, ttl=300)  # 5 minutes

def reset_login_attempts(db: Session, user: User, ip_address: str):
    """Reset failed login attempts"""
    if user.login_attempts > 0:
        user.login_attempts = 0
        user.locked_until = None
        db.commit()
    
    # Clear IP-based attempts
    cache_key = LOGIN_ATTEMPTS_CACHE_KEY.format(ip=ip_address)
    CacheUtils.delete(cache_key)

def check_login_security(ip_address: str) -> bool:
    """Check if login is allowed from this IP"""
    cache_key = LOGIN_ATTEMPTS_CACHE_KEY.format(ip=ip_address)
    attempts = CacheUtils.get(cache_key) or 0
    
    # Block IP after 10 failed attempts
    if attempts >= 10:
        logger.warning(f"IP {ip_address} blocked due to too many failed login attempts")
        return False
    
    return True

# Routes
@router.post("/register", response_model=SuccessResponse)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Register a new user
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
                detail="Tên đăng nhập đã được đăng ký"
            )
        
        # Check if email already exists
        existing_email = db.query(User).filter(
            User.email == user_data.email
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email đã được đăng ký"
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
            role=user_data.role
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
        
        # Log activity
        if request:
            log_activity(
                db, user.id, "User registered",
                ip_address=request.client.host,
                details=f"Registered with role: {user.role.value}"
            )
        
        logger.info(f"New user registered: {user.username} ({user.email})")
        
        return SuccessResponse(
            message="Registration successful. Please login.",
            data={
                "user_id": user.id,
                "username": user.username,
                "email": user.email
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đăng ký thất bại. Vui lòng thử lại."
        )

# Sử dụng dependencies parameter thay vì decorator
@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Login user and get access token
    """
    try:
        ip_address = request.client.host if request else "unknown"
        
        # Check login security for IP
        if not check_login_security(ip_address):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quá nhiều lần thử thất bại. Vui lòng thử lại sau."
            )
        
        # Normalize username - remove leading zeros
        input_username = login_data.username.lstrip('0') if login_data.username else login_data.username
        
        # Get user by normalized username or email
        user = db.query(User).filter(
            (User.username == input_username) | (User.email == login_data.username),
            User.is_deleted == False
        ).first()
        
        if not user:
            # Increment failed attempts for IP
            cache_key = LOGIN_ATTEMPTS_CACHE_KEY.format(ip=ip_address)
            attempts = CacheUtils.get(cache_key) or 0
            CacheUtils.set(cache_key, attempts + 1, ttl=300)
            
            logger.warning(f"Failed login attempt for non-existent user: {login_data.username} from {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác"
            )
        
        # Check if account is locked
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked until {user.locked_until}. Please try again later."
            )
        
        # Check if account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản đã bị vô hiệu hóa"
            )
        
        # Verify password
        if not user.verify_password(login_data.password):
            handle_failed_login(db, user, ip_address)
            
            logger.warning(f"Failed login attempt for user: {user.username} from {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác"
            )
        
        # Reset failed attempts on successful login
        reset_login_attempts(db, user, ip_address)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create tokens
        tokens = create_tokens(user)
        
        # Log activity
        log_activity(
            db, user.id, "User logged in",
            ip_address=ip_address,
            details="Login successful"
        )
        
        logger.info(f"User logged in: {user.username} from {ip_address}")
        
        return Token(**tokens)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đăng nhập thất bại. Vui lòng thử lại."
        )

# Hoặc sử dụng pre-configured rate limit function
@router.post("/login-v2", response_model=Token, dependencies=[login_rate_limit()])
async def login_v2(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Login with extended options (remember me, etc.)
    """
    try:
        ip_address = request.client.host if request else "unknown"
        
        # Check login security for IP
        if not check_login_security(ip_address):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quá nhiều lần thử thất bại. Vui lòng thử lại sau."
            )
        
        # Get user by username or email
        user = db.query(User).filter(
            (User.username == login_data.username) | (User.email == login_data.username),
            User.is_deleted == False
        ).first()
        
        if not user:
            # Increment failed attempts for IP
            cache_key = LOGIN_ATTEMPTS_CACHE_KEY.format(ip=ip_address)
            attempts = CacheUtils.get(cache_key) or 0
            CacheUtils.set(cache_key, attempts + 1, ttl=300)
            
            logger.warning(f"Failed login attempt for non-existent user: {login_data.username} from {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác"
            )
        
        # Check if account is locked
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked until {user.locked_until}. Please try again later."
            )
        
        # Check if account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tài khoản đã bị vô hiệu hóa"
            )
        
        # Verify password
        if not user.verify_password(login_data.password):
            handle_failed_login(db, user, ip_address)
            
            logger.warning(f"Failed login attempt for user: {user.username} from {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác"
            )
        
        # Reset failed attempts on successful login
        reset_login_attempts(db, user, ip_address)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Adjust token expiry for "remember me"
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES * (7 if login_data.remember_me else 1)
        )
        
        # Create tokens
        access_token = JWTUtils.create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "email": user.email
            },
            expires_delta=access_token_expires
        )
        
        refresh_token = JWTUtils.create_refresh_token(
            data={
                "sub": user.username,
                "user_id": user.id,
                "type": "refresh"
            }
        )
        
        # Log activity
        log_activity(
            db, user.id, "User logged in (v2)",
            ip_address=ip_address,
            details=f"Login successful, remember_me: {login_data.remember_me}"
        )
        
        logger.info(f"User logged in (v2): {user.username} from {ip_address}")
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=access_token_expires.seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login v2 error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đăng nhập thất bại. Vui lòng thử lại."
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    try:
        # Decode refresh token
        payload = JWTUtils.decode_token(token_data.refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token làm mới không hợp lệ"
            )
        
        # Get user
        user_id = payload.get("user_id")
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Không tìm thấy người dùng"
            )
        
        # Check if account is locked
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Tài khoản đã bị khóa"
            )
        
        # Create new tokens
        tokens = create_tokens(user)
        
        logger.info(f"Token refreshed for user: {user.username}")
        
        return Token(**tokens)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token làm mới không hợp lệ"
        )

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Logout user (invalidate token on client side)
    """
    try:
        # Log activity
        log_activity(
            db, current_user.id, "User logged out",
            ip_address=request.client.host if request else None,
            details="Logout successful"
        )
        
        logger.info(f"User logged out: {current_user.username}")
        
        return SuccessResponse(message="Logout successful")
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đăng xuất thất bại"
        )

@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Change user password
    """
    try:
        # Verify current password
        if not current_user.verify_password(password_data.old_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác"
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
        current_user.login_attempts = 0  # Reset failed attempts
        current_user.locked_until = None
        
        db.commit()
        
        # Log activity
        log_activity(
            db, current_user.id, "Password changed",
            ip_address=request.client.host if request else None,
            details="Password changed successfully"
        )
        
        logger.info(f"Password changed for user: {current_user.username}")
        
        return SuccessResponse(message="Password changed successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể thay đổi mật khẩu"
        )

@router.post("/forgot-password", response_model=SuccessResponse, dependencies=[rate_limit(identifier="forgot_password", limit=3, window=300)])  # 3 requests per 5 minutes
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Request password reset
    """
    try:
        # Find user by email
        user = db.query(User).filter(
            User.email == forgot_data.email,
            User.is_active == True,
            User.is_deleted == False
        ).first()
        
        if not user:
            # Don't reveal if user exists or not for security
            logger.info(f"Password reset requested for non-existent email: {forgot_data.email}")
            return SuccessResponse(
                message="If the email exists, a reset link will be sent"
            )
        
        # Generate reset token
        reset_token = SecurityUtils.generate_token(32)
        
        # Store token in cache (valid for 24 hours)
        cache_key = f"password_reset:{reset_token}"
        CacheUtils.set(cache_key, user.id, ttl=86400)
        
        # Send reset email in background
        background_tasks.add_task(
            EmailUtils.send_password_reset_email,
            user,
            reset_token
        )
        
        # Log activity
        log_activity(
            db, user.id, "Password reset requested",
            ip_address=request.client.host if request else None,
            details=f"Reset token generated for email: {forgot_data.email}"
        )
        
        logger.info(f"Password reset requested for user: {user.username}")
        
        return SuccessResponse(
            message="If the email exists, a reset link will be sent"
        )
        
    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xử lý yêu cầu đặt lại mật khẩu"
        )

@router.post("/reset-password", response_model=SuccessResponse, dependencies=[rate_limit(identifier="reset_password", limit=5, window=300)])  # 5 requests per 5 minutes
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Reset password using token
    """
    try:
        # Check if token exists in cache
        cache_key = f"password_reset:{reset_data.token}"
        user_id = CacheUtils.get(cache_key)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn"
            )
        
        # Get user
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,
            User.is_deleted == False
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không tìm thấy người dùng"
            )
        
        # Validate new password
        is_valid, errors = ValidationUtils.validate_password(reset_data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(errors)
            )
        
        # Set new password
        user.set_password(reset_data.new_password)
        user.login_attempts = 0
        user.locked_until = None
        
        db.commit()
        
        # Remove used token
        CacheUtils.delete(cache_key)
        
        # Log activity
        log_activity(
            db, user.id, "Password reset completed",
            ip_address=request.client.host if request else None,
            details="Password reset via token"
        )
        
        logger.info(f"Password reset for user: {user.username}")
        
        return SuccessResponse(message="Password reset successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể đặt lại mật khẩu"
        )

@router.post("/verify-2fa", response_model=SuccessResponse, dependencies=[rate_limit(identifier="2fa", limit=10, window=60)])  # 10 attempts per minute
async def verify_2fa(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify 2FA token
    """
    try:
        if not current_user.two_factor_enabled or not current_user.two_factor_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Xác thực 2 bước chưa được bật cho tài khoản này"
            )
        
        # Verify token
        if not SecurityUtils.verify_2fa_token(current_user.two_factor_secret, token):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã xác thực 2 bước không hợp lệ"
            )
        
        # Log activity
        log_activity(
            db, current_user.id, "2FA verified",
            details="2FA token verified successfully"
        )
        
        return SuccessResponse(message="2FA verification successful")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Xác thực 2 bước thất bại"
        )

@router.post("/enable-2fa", response_model=SuccessResponse)
async def enable_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable 2FA for user account
    """
    try:
        if current_user.two_factor_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Xác thực 2 bước đã được bật"
            )
        
        # Generate new secret
        secret = SecurityUtils.generate_2fa_secret()
        current_user.two_factor_secret = secret
        
        db.commit()
        
        # Log activity
        log_activity(
            db, current_user.id, "2FA enabled",
            details="2FA enabled for account"
        )
        
        logger.info(f"2FA enabled for user: {current_user.username}")
        
        return SuccessResponse(
            message="2FA enabled. Please scan QR code with authenticator app.",
            data={"secret": secret}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enable 2FA error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể bật xác thực 2 bước"
        )

@router.post("/disable-2fa", response_model=SuccessResponse)
async def disable_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable 2FA for user account
    """
    try:
        if not current_user.two_factor_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Xác thực 2 bước chưa được bật"
            )
        
        # Disable 2FA
        current_user.two_factor_enabled = False
        current_user.two_factor_secret = None
        
        db.commit()
        
        # Log activity
        log_activity(
            db, current_user.id, "2FA disabled",
            details="2FA disabled for account"
        )
        
        logger.info(f"2FA disabled for user: {current_user.username}")
        
        return SuccessResponse(message="2FA disabled successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Disable 2FA error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tắt xác thực 2 bước"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    """
    return current_user

@router.get("/sessions")
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's active sessions
    """
    try:
        # In a real implementation, you would query sessions from database
        # For now, return mock data
        return {
            "success": True,
            "sessions": [
                {
                    "id": 1,
                    "ip_address": "192.168.1.1",
                    "user_agent": "Mozilla/5.0",
                    "created_at": datetime.utcnow().isoformat(),
                    "last_accessed": datetime.utcnow().isoformat()
                }
            ]
        }
    except Exception as e:
        logger.error(f"Get sessions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy danh sách phiên đăng nhập"
        )

@router.post("/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a user session
    """
    try:
        # In a real implementation, you would mark session as revoked
        # For now, just return success
        return SuccessResponse(message="Session revoked successfully")
    except Exception as e:
        logger.error(f"Revoke session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể hủy phiên đăng nhập"
        )

@router.get("/check-username/{username}", dependencies=[rate_limit(identifier="check_username", limit=20, window=60)])  # 20 requests per minute
async def check_username_availability(
    username: str,
    db: Session = Depends(get_db)
):
    """
    Check if username is available
    """
    try:
        user = db.query(User).filter(User.username == username).first()
        available = user is None
        
        return {
            "success": True,
            "available": available,
            "username": username
        }
    except Exception as e:
        logger.error(f"Check username error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể kiểm tra tên đăng nhập"
        )

@router.get("/check-email/{email}", dependencies=[rate_limit(identifier="check_email", limit=20, window=60)])  # 20 requests per minute
async def check_email_availability(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Check if email is available
    """
    try:
        # Validate email format
        if not ValidationUtils.validate_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng email không hợp lệ"
            )
        
        user = db.query(User).filter(User.email == email).first()
        available = user is None
        
        return {
            "success": True,
            "available": available,
            "email": email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check email error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể kiểm tra email"
        )

@router.get("/activities", response_model=Dict[str, Any])
async def get_user_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    limit: int = 20
):
    """
    Get user activity logs
    """
    try:
        # Query activities
        activities = db.query(ActivityLog).filter(
            ActivityLog.user_id == current_user.id
        ).order_by(
            ActivityLog.created_at.desc()
        ).offset((page - 1) * limit).limit(limit).all()
        
        # Count total
        total = db.query(ActivityLog).filter(
            ActivityLog.user_id == current_user.id
        ).count()
        
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
                    "details": activity.details
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
    except Exception as e:
        logger.error(f"Get activities error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lấy lịch sử hoạt động"
        )

@router.post("/lock-account/{user_id}")
async def lock_user_account(
    user_id: int,
    duration_minutes: int = 30,
    reason: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lock user account (admin only)
    """
    try:
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ quản trị viên mới được khóa tài khoản"
            )
        
        # Get target user
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )
        
        # Can't lock admin accounts
        if target_user.role == UserRole.ADMIN and current_user.id != target_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không thể khóa tài khoản quản trị viên"
            )
        
        # Lock account
        target_user.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        db.commit()
        
        # Log activity
        log_activity(
            db, current_user.id, "Account locked",
            details=f"Locked account {target_user.username} for {duration_minutes} minutes. Reason: {reason}"
        )
        
        logger.warning(f"Account {target_user.username} locked by {current_user.username} for {duration_minutes} minutes")
        
        return SuccessResponse(
            message=f"Account locked for {duration_minutes} minutes",
            data={
                "user_id": target_user.id,
                "username": target_user.username,
                "locked_until": target_user.locked_until.isoformat(),
                "locked_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lock account error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể khóa tài khoản"
        )

@router.post("/unlock-account/{user_id}")
async def unlock_user_account(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlock user account (admin only)
    """
    try:
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ quản trị viên mới được mở khóa tài khoản"
            )
        
        # Get target user
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )
        
        # Unlock account
        target_user.locked_until = None
        target_user.login_attempts = 0
        db.commit()
        
        # Log activity
        log_activity(
            db, current_user.id, "Account unlocked",
            details=f"Unlocked account {target_user.username}"
        )
        
        logger.info(f"Account {target_user.username} unlocked by {current_user.username}")
        
        return SuccessResponse(
            message="Account unlocked successfully",
            data={
                "user_id": target_user.id,
                "username": target_user.username,
                "unlocked_by": current_user.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock account error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể mở khóa tài khoản"
        )

# Health check endpoint
@router.get("/health")
async def auth_health():
    """
    Authentication service health check
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "jwt": True,
            "password_hashing": True,
            "rate_limiting": True,
            "activity_logging": True
        }
    }


# ===== AGENT MOBILE APP ENDPOINTS =====

@router.post("/agent-login")
async def agent_login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Agent mobile app login endpoint
    Agent logs in with username (ID) and password
    User must have an active Agent record linked to their account
    """
    try:
        # Normalize username - remove leading zeros
        input_username = credentials.username.lstrip('0') if credentials.username else credentials.username
        
        logger.info(f"Agent login attempt: input={credentials.username}, normalized={input_username}")
        
        # Get user by normalized username only
        user = db.query(User).filter(User.username == input_username).first()
        
        logger.info(f"User found: {user.username if user else 'None'}")
        
        if not user:
            logger.warning(f"User not found for username: {input_username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác"
            )
        
        pwd_verify = SecurityUtils.verify_password(credentials.password, user.password_hash)
        logger.info(f"Password verify result: {pwd_verify}")
        
        if not pwd_verify:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản đã bị vô hiệu hóa"
            )
        
        # Check if user has an agent record (account has been activated as Agent)
        agent = db.query(Agent).filter(Agent.user_id == user.id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản chưa được kích hoạt Đại Lý. Vui lòng liên hệ quản trị viên."
            )
        
        if agent.status != AgentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Đại Lý chưa được kích hoạt. Trạng thái: {agent.status.value}"
            )
        
        # Create token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = JWTUtils.create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "agent_id": agent.id
            },
            expires_delta=access_token_expires
        )
        
        # Log activity
        activity = ActivityLog(
            user_id=user.id,
            activity_type="login",
            action="agent_mobile_login",
            resource_type="agent",
            resource_id=agent.id,
            details=f"Agent mobile app login from agent {agent.agent_code}"
        )
        db.add(activity)
        db.commit()
        
        logger.info(f"Agent {agent.agent_code} logged in via mobile app")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "agent_id": agent.id,
            "agent_code": agent.agent_code,
            "agent_name": agent.agent_name,
            "username": user.username,
            "email": user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi đăng nhập"
        )



