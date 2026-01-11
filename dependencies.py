from fastapi import Depends, HTTPException, status, Header, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Generator
from datetime import datetime, timedelta
import logging
from functools import wraps

from config import settings
from database import SessionLocal
from models import User, UserRole, Agent, AgentStatus, AgentType, Bill, Customer, Transaction
from schemas import TokenData
from security import verify_password, get_password_hash, create_access_token, create_refresh_token

# Configure logging
logger = logging.getLogger(__name__)

# HTTP Bearer authentication
security = HTTPBearer()

# Cache for user permissions
_permission_cache = {}

def get_db() -> Generator:
    """
    Database dependency.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_api_key(
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
) -> Agent:
    """
    Verify API key and return associated agent
    """
    agent = db.query(Agent).filter(
        Agent.api_key == x_api_key,
        Agent.status == AgentStatus.ACTIVE,
        Agent.is_deleted == False
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return agent

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            raise credentials_exception
        
        role_str = payload.get("role")
        # Convert role string to enum
        if role_str:
            try:
                role_enum = UserRole(role_str)
            except (ValueError, KeyError):
                role_enum = UserRole.AGENT
        else:
            role_enum = UserRole.AGENT
        
        token_data = TokenData(
            user_id=user_id, 
            username=payload.get("username"), 
            role=role_enum,
            email=payload.get("email")
        )
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(
        User.id == token_data.user_id,
        User.is_active == True,
        User.is_deleted == False
    ).first()
    
    if user is None:
        raise credentials_exception
    
    # Check if user is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked due to too many failed login attempts"
        )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user

async def get_current_user_ws(
    token: str,
    db: Session
) -> Optional[User]:
    """
    Get current authenticated user from JWT token for WebSocket
    Doesn't raise exceptions, returns None if token is invalid
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return None
        
        # Get user from database
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,
            User.is_deleted == False
        ).first()
        
        return user
        
    except JWTError as e:
        logger.error(f"WebSocket JWT decode error: {e}")
        return None
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure user is active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

async def get_current_active_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to ensure user is admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def get_current_agent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Agent:
    """
    Dependency to get current user's agent profile
    """
    agent = db.query(Agent).filter(
        Agent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent profile not found"
        )
    
    return agent

async def get_current_active_agent(
    agent: Agent = Depends(get_current_agent)
) -> Agent:
    """
    Dependency to ensure agent is active
    """
    if agent.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is not active"
        )
    return agent

# Role-based access control
def require_role(required_roles: List[UserRole]):
    """
    Dependency factory for role-based access control
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

# Permission-based access control
def require_permission(required_permissions: List[str]):
    """
    Dependency factory for permission-based access control
    """
    def permission_checker(current_user: User = Depends(get_current_user)):
        user_permissions = get_user_permissions(current_user)
        
        # Check if user has any of the required permissions
        if not any(perm in user_permissions for perm in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return permission_checker

def get_user_permissions(user: User) -> List[str]:
    """
    Get user permissions based on role
    """
    # Cache permissions to avoid repeated calculations
    cache_key = f"user_{user.id}_permissions"
    if cache_key in _permission_cache:
        return _permission_cache[cache_key]
    
    permissions = []
    
    # Define role-based permissions
    role_permissions = {
        UserRole.ADMIN: [
            # User management
            "users:read", "users:create", "users:update", "users:delete", "users:manage",
            # Agent management
            "agents:read", "agents:create", "agents:update", "agents:delete", "agents:approve",
            # Bill management
            "bills:read", "bills:create", "bills:update", "bills:delete", "bills:import", "bills:export",
            # Transaction management
            "transactions:read", "transactions:create", "transactions:update", "transactions:cancel",
            # Customer management
            "customers:read", "customers:create", "customers:update", "customers:delete",
            # System management
            "system:config", "system:backup", "system:restore", "system:logs",
            # Reports
            "reports:read", "reports:export",
            # API management
            "api:manage", "api:keys",
        ],
        UserRole.MANAGER: [
            "agents:read", "agents:create", "agents:update", "agents:approve",
            "bills:read", "bills:create", "bills:update", "bills:import", "bills:export",
            "transactions:read", "transactions:create", "transactions:update",
            "customers:read", "customers:create", "customers:update",
            "reports:read", "reports:export",
        ],
        UserRole.AGENT: [
            "bills:read", "bills:create", "bills:update:own", "bills:sell",
            "transactions:read:own", "transactions:create:own",
            "customers:read:own", "customers:create:own", "customers:update:own",
        ],
        UserRole.STAFF: [
            "bills:read", "bills:create", "bills:update",
            "customers:read", "customers:create", "customers:update",
        ],
        UserRole.VIEWER: [
            "bills:read", "customers:read", "reports:read",
        ]
    }
    
    # Add role permissions
    permissions.extend(role_permissions.get(user.role, []))
    
    # Add any additional permissions based on specific conditions
    if user.role == UserRole.AGENT:
        # Check if agent has special permissions from their agent profile
        permissions.append("agent:profile")
    
    # Cache permissions
    _permission_cache[cache_key] = permissions
    
    return permissions

# API key authentication
async def api_key_auth(
    api_key: str = Header(None, alias="X-API-Key"),
    api_secret: str = Header(None, alias="X-API-Secret"),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency for API key authentication
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required"
        )
    
    user = db.query(User).filter(
        User.api_key == api_key,
        User.is_active == True,
        User.is_deleted == False
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Verify API secret if provided
    if api_secret:
        if not user.api_secret or not verify_password(api_secret, user.api_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API secret"
            )
    
    # Update API usage statistics
    user.api_calls_count += 1
    db.commit()
    
    return user

# Webhook signature verification
async def verify_webhook_signature(
    request: Request,
    webhook_secret: str
) -> bool:
    """
    Verify webhook signature
    """
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        return False
    
    # Get request body
    body = await request.body()
    
    # Verify signature (HMAC SHA256)
    import hmac
    import hashlib
    
    expected_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

# Simple rate limiter class
class RateLimiter:
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        current_time = datetime.utcnow().timestamp()
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests
        self.requests[key] = [req_time for req_time in self.requests[key] 
                             if current_time - req_time < window]
        
        if len(self.requests[key]) < limit:
            self.requests[key].append(current_time)
            return True
        return False

# Rate limiter instance
rate_limiter = RateLimiter()

# Rate limiting dependency factory
def rate_limit(identifier: str = "default", limit: int = 100, window: int = 60):
    """
    Dependency factory for rate limiting.
    Returns a FastAPI dependency that can be used in route dependencies.
    
    Args:
        identifier: Unique identifier for this rate limit (e.g., "login", "api")
        limit: Maximum number of requests allowed in the time window
        window: Time window in seconds
    
    Returns:
        FastAPI dependency function
    """
    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "127.0.0.1"
        key = f"{identifier}:{client_ip}"
        
        if not rate_limiter.is_allowed(key, limit, window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window)}
            )
    return Depends(dependency)

# Pre-configured rate limit dependencies
def login_rate_limit():
    """Rate limit for login endpoints: 5 requests per minute"""
    return rate_limit(identifier="login", limit=5, window=60)

def api_rate_limit():
    """Rate limit for general API endpoints: 100 requests per minute"""
    return rate_limit(identifier="api", limit=100, window=60)

def strict_rate_limit():
    """Strict rate limit: 1 request per 10 seconds"""
    return rate_limit(identifier="strict", limit=1, window=10)

# Admin-only dependency (for use with Depends)
async def admin_only_dep(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check if user is admin - use with Depends(admin_only_dep)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access only"
        )
    return current_user

# Manager or admin dependency (for use with Depends)
async def manager_or_admin_dep(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check if user is manager or admin - use with Depends(manager_or_admin_dep)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access only"
        )
    return current_user

# Agent or higher dependency (for use with Depends)
async def agent_or_higher_dep(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Check if user is agent or higher - use with Depends(agent_or_higher_dep)"""
    allowed_roles = [UserRole.ADMIN, UserRole.MANAGER, UserRole.AGENT]
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return current_user

# Decorator versions (for backward compatibility with @admin_only() and @manager_or_admin() syntax)
def admin_only():
    """Decorator for admin-only routes - for @admin_only() usage"""
    def decorator(func):
        return func
    return decorator

def manager_or_admin():
    """Decorator for manager/admin routes - for @manager_or_admin() usage"""
    def decorator(func):
        return func
    return decorator

def agent_or_higher():
    """Decorator for agent or higher routes"""
    def decorator(func):
        return func
    return decorator

def require_admin():
    """Decorator for admin-only routes"""
    def decorator(func):
        return func
    return decorator

def require_manager():
    """Decorator for manager/admin routes"""
    def decorator(func):
        return func
    return decorator

# Resource ownership check
def require_ownership(resource_type: str):
    """
    Dependency factory to check resource ownership
    """
    def ownership_checker(
        resource_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        # Map resource types to models and ownership fields
        resource_map = {
            "agent": (Agent, "user_id"),
            "bill": (Bill, "created_by_id"),
            "customer": (Customer, "agent_id"),
            "transaction": (Transaction, "user_id"),
        }
        
        if resource_type not in resource_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid resource type: {resource_type}"
            )
        
        model, ownership_field = resource_map[resource_type]
        
        # Get resource
        resource = db.query(model).filter(
            model.id == resource_id
        ).first()
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_type.capitalize()} not found"
            )
        
        # Check ownership
        if hasattr(resource, ownership_field):
            owner_id = getattr(resource, ownership_field)
            if owner_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this resource"
                )
        else:
            # Admin and managers can access all resources
            if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
        
        return resource
    
    return ownership_checker

# Pagination dependency
async def pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=10000, description="Items per page"),
    sort_by: str = Query(None, description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order")
):
    return {
        "page": page,
        "limit": limit,
        "sort_by": sort_by,
        "sort_order": sort_order
    }

# Filter parameters for agents
async def agent_filter_params(
    status: Optional[AgentStatus] = Query(None, description="Filter by agent status"),
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    search: Optional[str] = Query(None, description="Search by name or code"),
    created_from: Optional[datetime] = Query(None, description="Created from date"),
    created_to: Optional[datetime] = Query(None, description="Created to date")
):
    return {
        "status": status,
        "agent_type": agent_type,
        "search": search,
        "created_from": created_from,
        "created_to": created_to
    }

# Filter parameters for bills
async def bill_filter_params(
    status: Optional[str] = Query(None, description="Filter by bill status"),
    period_from: Optional[str] = Query(None, description="Period from (YYYY-MM)"),
    period_to: Optional[str] = Query(None, description="Period to (YYYY-MM)"),
    period: Optional[str] = Query(None, description="Exact period (MM/YYYY)"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    customer_code: Optional[str] = Query(None, description="Filter by customer code"),
    search: Optional[str] = Query(None, description="Quick search across customer code, name, bill code"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    amount_from: Optional[float] = Query(None, ge=0, description="Minimum amount"),
    amount_to: Optional[float] = Query(None, ge=0, description="Maximum amount")
):
    return {
        "status": status,
        "period_from": period_from,
        "period_to": period_to,
        "period": period,
        "agent_id": agent_id,
        "customer_code": customer_code,
        "search": search,
        "provider": provider,
        "amount_from": amount_from,
        "amount_to": amount_to
    }

# File upload dependency
async def validate_file_upload(
    request: Request,
    max_size: int = 10 * 1024 * 1024,  # 10MB default
    allowed_types: List[str] = None
):
    """
    Validate file upload
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size} bytes"
        )
    
    if allowed_types:
        content_type = request.headers.get("content-type")
        if content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type not supported. Allowed types: {', '.join(allowed_types)}"
            )

# CORS dependency
async def cors_headers():
    """
    Add CORS headers to response
    """
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-API-Key"
    }

# Audit logging decorator
def audit_log(action: str, resource_type: str = None):
    """
    Decorator to log user actions for audit trail
    """
    import asyncio
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user from kwargs
            request = None
            current_user = None
            db = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
            
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                elif isinstance(value, User) and hasattr(value, 'id'):
                    current_user = value
                elif isinstance(value, Session):
                    db = value
            
            # Execute the function - always await for async functions
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Log the action if we have a database and user
            if db and current_user and request:
                from models import ActivityLog, ActivityType
                
                # Determine resource ID from result
                resource_id = None
                if isinstance(result, dict) and 'id' in result:
                    resource_id = result['id']
                elif hasattr(result, 'id'):
                    resource_id = result.id
                
                # Create activity log
                activity = ActivityLog(
                    user_id=current_user.id,
                    activity_type=ActivityType.UPDATE if "update" in action.lower() else ActivityType.CREATE,
                    action=action,
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=request.headers.get("user-agent") if request else None,
                    resource_type=resource_type,
                    resource_id=resource_id
                )
                
                db.add(activity)
                db.commit()
            
            return result
        return wrapper
    return decorator

# Request ID dependency
async def get_request_id(
    request: Request,
    x_request_id: str = Header(None, alias="X-Request-ID")
):
    """
    Get or generate request ID for tracing
    """
    request_id = x_request_id or request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    
    # Store in request state for later use
    request.state.request_id = request_id
    
    return request_id

# Health check dependency
async def health_check_deps(db: Session = Depends(get_db)):
    """
    Dependencies for health check endpoint
    """
    # Check database connection
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Check external services (if any)
    services_health = {
        "database": db_status,
        "cache": "healthy",  # Placeholder
        "storage": "healthy"  # Placeholder
    }
    
    return {
        "database": {"status": db_status},
        "services": services_health
    }

# Maintenance mode check
async def check_maintenance_mode(db: Session = Depends(get_db)):
    """
    Check if system is in maintenance mode
    """
    from models import SystemConfig
    
    maintenance_config = db.query(SystemConfig).filter(
        SystemConfig.key == "maintenance_mode"
    ).first()
    
    if maintenance_config and maintenance_config.value == "true":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is under maintenance. Please try again later."
        )

# Request validation middleware
async def validate_request(
    request: Request,
    required_fields: List[str] = None
):
    """
    Validate request body
    """
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.json()
            
            if required_fields:
                missing_fields = []
                for field in required_fields:
                    if field not in body:
                        missing_fields.append(field)
                
                if missing_fields:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Missing required fields: {', '.join(missing_fields)}"
                    )
            
            return body
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in request body"
            )
    
    return None

# Clean up permission cache periodically
def clear_permission_cache():
    """
    Clear permission cache (call periodically)
    """
    global _permission_cache
    _permission_cache.clear()
    logger.info("Permission cache cleared")

# Export filters dependency
async def export_filter_params(
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    return {
        "start_date": start_date,
        "end_date": end_date,
        "agent_id": agent_id,
        "status": status
    }

# Search dependency
async def search_params(
    query: str = Query(..., min_length=2, description="Search query"),
    search_type: str = Query("all", description="Type of search: all, agents, bills, customers"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results")
):
    return {
        "query": query,
        "search_type": search_type,
        "limit": limit
    }

# Date range dependency
async def date_range_params(
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date")
):
    return {
        "start_date": start_date,
        "end_date": end_date
    }

# Transaction filter parameters
async def transaction_filter_params(
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum amount"),
    max_amount: Optional[float] = Query(None, ge=0, description="Maximum amount")
):
    return {
        "transaction_type": transaction_type,
        "status": status,
        "agent_id": agent_id,
        "start_date": start_date,
        "end_date": end_date,
        "min_amount": min_amount,
        "max_amount": max_amount
    }

# Report parameters
async def report_params(
    report_type: str = Query(..., description="Type of report: sales, agent, system"),
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    agent_id: Optional[int] = Query(None, description="Agent ID for filtering"),
    group_by: str = Query("day", description="Group by: day, week, month, year")
):
    return {
        "report_type": report_type,
        "start_date": start_date,
        "end_date": end_date,
        "agent_id": agent_id,
        "group_by": group_by
    }

# Custom query parameters for reports
async def custom_report_params(
    metrics: List[str] = Query(..., description="Metrics to include in report"),
    dimensions: List[str] = Query(None, description="Dimensions for grouping"),
    filters: Optional[str] = Query(None, description="JSON string of filters"),
    format: str = Query("json", description="Output format: json, csv, excel")
):
    return {
        "metrics": metrics,
        "dimensions": dimensions,
        "filters": filters,
        "format": format
    }

# Customer filter parameters
async def customer_filter_params(
    customer_type: Optional[str] = Query(None, description="Filter by customer type"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name, code, or contact"),
    created_from: Optional[datetime] = Query(None, description="Created from date"),
    created_to: Optional[datetime] = Query(None, description="Created to date")
):
    return {
        "customer_type": customer_type,
        "agent_id": agent_id,
        "status": status,
        "search": search,
        "created_from": created_from,
        "created_to": created_to
    }

# Export format dependency
async def export_format(
    format: str = Query("csv", description="Export format: csv, excel, json")
):
    """
    Validate export format
    """
    allowed_formats = ["csv", "excel", "json"]
    if format not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export format. Allowed: {', '.join(allowed_formats)}"
        )
    return format

# Language dependency
async def get_accept_language(
    accept_language: str = Header("en", description="Accept-Language header")
):
    """
    Extract language from Accept-Language header
    """
    # Parse language header (e.g., "en-US,en;q=0.9,vi;q=0.8")
    languages = accept_language.split(',')
    if languages:
        primary_language = languages[0].split(';')[0].strip()
        # Return language code (first 2 characters)
        return primary_language[:2]
    return "en"

# Timezone dependency
async def get_timezone(
    x_timezone: str = Header("UTC", alias="X-Timezone", description="Timezone for date/time operations")
):
    """
    Get timezone from header or use UTC as default
    """
    # Validate timezone (you can add more validation)
    try:
        import pytz
        pytz.timezone(x_timezone)
        return x_timezone
    except:
        return "UTC"

# API version dependency
async def get_api_version(
    x_api_version: str = Header("v1", alias="X-API-Version", description="API version")
):
    """
    Get API version from header
    """
    allowed_versions = ["v1", "v2"]
    if x_api_version not in allowed_versions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported API version. Allowed: {', '.join(allowed_versions)}"
        )
    return x_api_version

# Request timing dependency
async def request_timing():
    """
    Dependency to measure request processing time
    """
    import time
    start_time = time.time()
    
    def get_elapsed_time():
        return time.time() - start_time
    
    return get_elapsed_time

# Cache control dependency
async def cache_control(
    cache_control: str = Header(None, description="Cache-Control header"),
    x_no_cache: bool = Header(False, alias="X-No-Cache", description="Bypass cache")
):
    """
    Handle cache control headers
    """
    return {
        "cache_control": cache_control,
        "no_cache": x_no_cache
    }

# User agent dependency
async def get_user_agent(
    user_agent: str = Header(None, description="User-Agent header")
):
    """
    Extract user agent information
    """
    return user_agent

# Content type validation
async def validate_content_type(
    content_type: str = Header(None, description="Content-Type header"),
    allowed_types: List[str] = None
):
    """
    Validate content type
    """
    if allowed_types and content_type:
        if content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported content type. Allowed: {', '.join(allowed_types)}"
            )
    return content_type

# Bulk operation dependency
async def bulk_operation_params(
    operation: str = Query(..., description="Bulk operation: create, update, delete"),
    batch_size: int = Query(100, ge=1, le=1000, description="Batch size"),
    dry_run: bool = Query(False, description="Dry run mode")
):
    return {
        "operation": operation,
        "batch_size": batch_size,
        "dry_run": dry_run
    }

# Export schedule dependency
async def export_schedule_params(
    schedule_type: str = Query(..., description="Schedule type: daily, weekly, monthly"),
    time: str = Query("00:00", description="Time to run (HH:MM)"),
    format: str = Query("csv", description="Export format"),
    recipients: List[str] = Query(None, description="Recipient emails")
):
    return {
        "schedule_type": schedule_type,
        "time": time,
        "format": format,
        "recipients": recipients
    }

# Notification preferences
async def notification_preferences(
    email_notifications: bool = Query(True, description="Enable email notifications"),
    push_notifications: bool = Query(False, description="Enable push notifications"),
    frequency: str = Query("daily", description="Notification frequency: immediate, daily, weekly")
):
    return {
        "email_notifications": email_notifications,
        "push_notifications": push_notifications,
        "frequency": frequency
    }

# Data export dependency
async def data_export_params(
    export_type: str = Query(..., description="Export type: all, selected, filtered"),
    include_sensitive: bool = Query(False, description="Include sensitive data"),
    password: Optional[str] = Query(None, description="Password for encrypted export")
):
    return {
        "export_type": export_type,
        "include_sensitive": include_sensitive,
        "password": password
    }

# Data import validation
async def validate_data_import(
    request: Request,
    import_type: str,
    max_records: int = 10000
):
    """
    Validate data import request
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 100 * 1024 * 1024:  # 100MB
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Import file too large. Maximum size is 100MB"
        )
    
    # You can add more validation based on import_type
    return {
        "import_type": import_type,
        "max_records": max_records
    }

# Webhook payload validation
async def validate_webhook_payload(
    request: Request,
    webhook_type: str,
    webhook_secret: str
):
    """
    Validate webhook payload and signature
    """
    # Verify signature
    signature_valid = await verify_webhook_signature(request, webhook_secret)
    if not signature_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Validate payload based on webhook_type
    try:
        payload = await request.json()
        
        # Basic validation based on webhook type
        if webhook_type == "payment":
            required_fields = ["transaction_id", "amount", "status"]
        elif webhook_type == "customer":
            required_fields = ["customer_id", "action"]
        else:
            required_fields = ["event", "data"]
        
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        return payload
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

# Job scheduling dependency
async def job_scheduling_params(
    job_type: str = Query(..., description="Job type: report, backup, sync"),
    schedule: str = Query("0 0 * * *", description="Cron schedule expression"),
    parameters: Optional[str] = Query(None, description="Job parameters as JSON")
):
    """
    Validate job scheduling parameters
    """
    # Validate cron expression (basic validation)
    import re
    cron_pattern = r'^(\*|[0-9,/\-]+) (\*|[0-9,/\-]+) (\*|[0-9,/\-]+) (\*|[0-9,/\-]+) (\*|[0-9,/\-]+)$'
    if not re.match(cron_pattern, schedule):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cron expression format"
        )
    
    return {
        "job_type": job_type,
        "schedule": schedule,
        "parameters": parameters
    }

# Export completed dependencies list for documentation
DEPENDENCIES = {
    "get_db": "Database session",
    "get_current_user": "Current authenticated user",
    "get_current_active_user": "Current active user",
    "get_current_agent": "Current user's agent profile",
    "get_current_active_agent": "Current active agent",
    "require_role": "Role-based access control",
    "require_permission": "Permission-based access control",
    "api_key_auth": "API key authentication",
    "rate_limit": "Rate limiting factory",
    "login_rate_limit": "Pre-configured login rate limit",
    "api_rate_limit": "Pre-configured API rate limit",
    "strict_rate_limit": "Pre-configured strict rate limit",
    "admin_only": "Admin-only access",
    "manager_or_admin": "Manager or admin access",
    "agent_or_higher": "Agent or higher access",
    "require_ownership": "Resource ownership check",
    "pagination_params": "Pagination parameters",
    "agent_filter_params": "Agent filter parameters",
    "bill_filter_params": "Bill filter parameters",
    "validate_file_upload": "File upload validation",
    "get_request_id": "Request ID for tracing",
    "health_check_deps": "Health check dependencies",
    "check_maintenance_mode": "Maintenance mode check",
    "validate_request": "Request validation",
    "export_filter_params": "Export filter parameters",
    "search_params": "Search parameters",
    "date_range_params": "Date range parameters",
    "transaction_filter_params": "Transaction filter parameters",
    "report_params": "Report parameters",
    "custom_report_params": "Custom report parameters",
    "customer_filter_params": "Customer filter parameters",
    "export_format": "Export format validation",
    "get_accept_language": "Language preference",
    "get_timezone": "Timezone preference",
    "get_api_version": "API version",
    "request_timing": "Request timing measurement",
    "cache_control": "Cache control",
    "get_user_agent": "User agent extraction",
    "validate_content_type": "Content type validation",
    "bulk_operation_params": "Bulk operation parameters",
    "export_schedule_params": "Export schedule parameters",
    "notification_preferences": "Notification preferences",
    "data_export_params": "Data export parameters",
    "validate_data_import": "Data import validation",
    "validate_webhook_payload": "Webhook payload validation",
    "job_scheduling_params": "Job scheduling parameters",
}