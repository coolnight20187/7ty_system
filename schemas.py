from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any, TypeVar, Generic
from datetime import datetime, date
from enum import Enum
from decimal import Decimal

# Import enums from models
from models import (
    UserRole, AgentStatus, AgentType, TransactionStatus,
    TransactionType, BillStatus, ActivityType, NotificationType,
    NotificationStatus
)

# Generic TypeVar for pagination
T = TypeVar('T')

# Base schemas
class SuccessResponse(BaseModel):
    """Base success response schema"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class ErrorResponse(BaseModel):
    """Base error response schema"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class PaginationResponse(BaseModel):
    """Pagination metadata schema"""
    page: int
    limit: int
    total: int
    pages: int

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema"""
    data: List[T]
    page: int
    limit: int
    total: int
    pages: int
    
    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    """Token data schema"""
    user_id: int
    username: str
    role: UserRole
    email: Optional[str] = None
    
    class Config:
        from_attributes = True

class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }

# Authentication schemas
class LoginRequest(BaseModel):
    """Login request schema"""
    username: str
    password: str
    remember_me: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "password": "SecurePass123!",
                "remember_me": False
            }
        }

class ChangePasswordRequest(BaseModel):
    """Change password request schema"""
    old_password: str
    new_password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "OldPass123!",
                "new_password": "NewSecurePass456!"
            }
        }

class AdminResetPasswordRequest(BaseModel):
    """Admin reset password request schema - no old password required"""
    new_password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_password": "NewSecurePass456!"
            }
        }

class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema"""
    email: EmailStr
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }

class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""
    token: str
    new_password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "reset_token_123",
                "new_password": "NewSecurePass456!"
            }
        }

# User schemas
class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: UserRole = UserRole.VIEWER
    
    class Config:
        from_attributes = True

class UserCreate(UserBase):
    """User creation schema"""
    password: str = Field(..., min_length=8)
    is_active: Optional[bool] = True
    
    @validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "phone": "+1234567890",
                "role": "agent",
                "password": "SecurePass123!",
                "is_active": True
            }
        }

class UserUpdate(BaseModel):
    """User update schema"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)
    gender: Optional[str] = Field(None, max_length=10)
    date_of_birth: Optional[date] = None
    address: Optional[str] = Field(None, max_length=500)
    ward: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    
    @validator('password')
    def validate_password_strength(cls, v):
        if v is not None:
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters long')
            if not any(c.isupper() for c in v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not any(c.islower() for c in v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not any(c.isdigit() for c in v):
                raise ValueError('Password must contain at least one digit')
            if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
                raise ValueError('Password must contain at least one special character')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe_updated",
                "email": "john.updated@example.com",
                "full_name": "John Doe Updated",
                "phone": "+0987654321",
                "role": "manager",
                "is_active": True
            }
        }

class UserRoleUpdate(BaseModel):
    """Schema for updating user role"""
    role: UserRole
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "role": "agent"
            }
        }

class UserResponse(UserBase):
    """User response schema"""
    id: int
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    ward: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None
    cccd_front: Optional[str] = None
    cccd_back: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserFilterParams(BaseModel):
    """Schema for user filter parameters"""
    search: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserSearchResult(BaseModel):
    """Schema for user search result"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    
    class Config:
        from_attributes = True

# Agent schemas
class AgentBase(BaseModel):
    """Base agent schema"""
    agent_code: str
    agent_name: Optional[str] = Field(None, max_length=100)
    agent_type: AgentType = AgentType.INDIVIDUAL
    company_name: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    store_address: Optional[str] = None
    status: AgentStatus = AgentStatus.PENDING
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    balance: Optional[Decimal] = Field(None, ge=0)
    daily_limit: Optional[Decimal] = None
    per_transaction_limit: Optional[Decimal] = None
    # Image paths
    cccd_front_path: Optional[str] = None
    cccd_back_path: Optional[str] = None
    store_image_1_path: Optional[str] = None
    store_image_2_path: Optional[str] = None
    store_image_3_path: Optional[str] = None
    
    class Config:
        from_attributes = True

class AgentCreate(AgentBase):
    """Agent creation schema"""
    user_id: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "agent_code": "AG202312310001",
                "agent_type": "individual",
                "company_name": "Doe Enterprises",
                "tax_code": "1234567890",
                "address": "123 Main St",
                "city": "Hanoi",
                "district": "Cau Giay",
                "ward": "Dich Vong",
                "status": "pending",
                "commission_rate": 5.5,
                "balance": 0
            }
        }

class AgentCreateWithUser(BaseModel):
    """Schema for creating agent with user data in one step"""
    # User data
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)
    full_name: str = Field(..., max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    
    # Agent data
    agent_name: str = Field(..., max_length=100, description="Tên Đại Lý")
    agent_code: str
    agent_type: AgentType = AgentType.INDIVIDUAL
    company_name: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    status: AgentStatus = AgentStatus.PENDING
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    
    @validator('password_confirm')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "agent_001",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "full_name": "Agent One",
                "phone": "+84123456789",
                "agent_name": "Đại Lý A",
                "agent_code": "AG-1701250000-1234",
                "agent_type": "individual",
                "company_name": "Company A",
                "tax_code": "1234567890",
                "address": "123 Main St",
                "city": "Hanoi",
                "district": "Cau Giay",
                "ward": "Dich Vong",
                "status": "pending",
                "commission_rate": 5.5
            }
        }

class AgentUpdate(BaseModel):
    """Agent update schema"""
    full_name: Optional[str] = Field(None, max_length=100)
    agent_name: Optional[str] = Field(None, max_length=100)
    agent_type: Optional[AgentType] = None
    company_name: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    status: Optional[AgentStatus] = None
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    notes: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Updated Name",
                "agent_name": "Updated Agent Name",
                "agent_type": "company",
                "company_name": "Updated Company",
                "status": "active",
                "commission_rate": 7.5
            }
        }

class AgentResponse(AgentBase):
    """Agent response schema"""
    id: int
    user_id: int
    user: Optional[UserResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_by_user: Optional[UserResponse] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class AgentStatsResponse(AgentResponse):
    """Agent statistics response schema"""
    total_bills: int = 0
    total_transactions: int = 0
    total_revenue: Decimal = Decimal('0.00')
    total_commission: Decimal = Decimal('0.00')
    average_rating: float = 0.0
    
    class Config:
        from_attributes = True

# Customer schemas
class CustomerBase(BaseModel):
    """Base customer schema"""
    customer_code: str
    full_name: Optional[str] = None
    customer_name: Optional[str] = None  # Alias for full_name in create
    customer_type: Optional[str] = "individual"
    id_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    status: Optional[str] = "active"
    
    class Config:
        from_attributes = True

class CustomerCreate(CustomerBase):
    """Customer creation schema"""
    agent_id: Optional[int] = None
    password: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": None,
                "customer_code": "THE123456",
                "customer_name": "Nguyen Van A",
                "customer_type": "individual",
                "id_number": "012345678901",
                "phone": "0901234567",
                "email": "nguyenvana@email.com",
                "address": "123 Đường ABC, Phường XYZ, Quận 1, TP.HCM",
                "city": None,
                "district": "Ba Dinh",
                "ward": "Ngoc Ha",
                "status": "active"
            }
        }

class CustomerUpdate(BaseModel):
    """Customer update schema"""
    customer_name: Optional[str] = None
    customer_type: Optional[str] = None
    id_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    status: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_name": "John Smith Updated",
                "phone": "+84987654321",
                "status": "inactive"
            }
        }

class CustomerResponse(BaseModel):
    """Customer response schema"""
    id: int
    customer_code: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    user_id: Optional[int] = None
    agent_id: Optional[int] = None
    agent: Optional[AgentResponse] = None
    
    # Credit card info
    bank_name: Optional[str] = None
    card_type: Optional[str] = None
    card_last_digits: Optional[str] = None
    card_cvv: Optional[str] = None
    card_expiry: Optional[str] = None
    card_holder_name: Optional[str] = None
    card_tier: Optional[str] = None
    billing_cycle: Optional[int] = None
    credit_limit: Optional[Decimal] = None
    customer_type: Optional[str] = None
    
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Bill schemas
class BillBase(BaseModel):
    """Base bill schema"""
    period: str  # Format: YYYY-MM
    customer_code: str
    customer_name: str
    address: Optional[str] = None
    amount: Decimal = Field(..., gt=0)
    due_date: date
    status: BillStatus = BillStatus.PENDING
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class BillCreate(BillBase):
    """Bill creation schema"""
    agent_id: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": 1,
                "period": "2023-12",
                "customer_code": "CUST001",
                "customer_name": "John Smith",
                "address": "456 Oak St, Hanoi",
                "amount": 1500000,
                "due_date": "2023-12-31",
                "status": "pending",
                "notes": "Monthly electricity bill"
            }
        }

class BillUpdate(BaseModel):
    """Bill update schema"""
    period: Optional[str] = None
    customer_code: Optional[str] = None
    customer_name: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    due_date: Optional[date] = None
    status: Optional[BillStatus] = None
    notes: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "amount": 1600000,
                "status": "paid",
                "notes": "Payment received"
            }
        }

class BillResponse(BaseModel):
    """Bill response schema - matches actual Bill model"""
    id: int
    bill_code: str
    customer_id: Optional[int] = None
    customer_code: str
    customer_name: str
    customer_address: Optional[str] = None
    customer_phone: Optional[str] = None
    evn_customer_code: Optional[str] = None
    period: str
    due_date: Optional[date] = None
    total_amount: Decimal
    electricity_amount: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    other_fees: Optional[Decimal] = None
    consumption: Optional[Decimal] = None
    previous_index: Optional[Decimal] = None
    current_index: Optional[Decimal] = None
    agent_id: Optional[int] = None
    agent_commission: Optional[Decimal] = None
    status: BillStatus
    payment_date: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_by: Optional[str] = None
    imported_file: Optional[str] = None
    imported_at: Optional[datetime] = None
    evn_bill_code: Optional[str] = None
    payment_method: Optional[str] = None
    transaction_ref: Optional[str] = None
    notes: Optional[str] = None
    provider: Optional[str] = None
    agent: Optional[AgentResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Transaction schemas
class TransactionBase(BaseModel):
    """Base transaction schema"""
    transaction_code: str
    transaction_type: TransactionType
    amount: Decimal = Field(..., gt=0)
    status: TransactionStatus = TransactionStatus.PENDING
    payment_method: str = "cash"
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True

class TransactionCreate(TransactionBase):
    """Transaction creation schema"""
    bill_id: Optional[int] = None
    agent_id: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "bill_id": 1,
                "agent_id": 1,
                "transaction_code": "TRX202312310001",
                "transaction_type": "payment",
                "amount": 1500000,
                "status": "pending",
                "payment_method": "bank_transfer",
                "notes": "Bill payment for December 2023"
            }
        }

class TransactionUpdate(BaseModel):
    """Transaction update schema"""
    transaction_type: Optional[TransactionType] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    status: Optional[TransactionStatus] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "payment_method": "credit_card",
                "notes": "Payment confirmed"
            }
        }

class TransactionResponse(TransactionBase):
    """Transaction response schema"""
    id: int
    bill_id: Optional[int] = None
    agent_id: Optional[int] = None
    user_id: Optional[int] = None
    bill: Optional[BillResponse] = None
    agent: Optional[AgentResponse] = None
    user: Optional[UserResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Activity log schemas
class ActivityLogBase(BaseModel):
    """Base activity log schema"""
    activity_type: ActivityType
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class ActivityLogCreate(ActivityLogBase):
    """Activity log creation schema"""
    user_id: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "activity_type": "login",
                "action": "User logged in",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0",
                "details": "Successful login",
                "resource_type": "user",
                "resource_id": 1
            }
        }

class ActivityLogResponse(ActivityLogBase):
    """Activity log response schema"""
    id: int
    user_id: int
    user: Optional[UserResponse] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Notification schemas
class NotificationBase(BaseModel):
    """Base notification schema"""
    notification_type: NotificationType
    title: str
    message: str
    status: NotificationStatus = NotificationStatus.UNREAD
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class NotificationCreate(NotificationBase):
    """Notification creation schema"""
    user_id: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "notification_type": "info",
                "title": "New Bill Added",
                "message": "A new bill has been added to your account",
                "status": "unread",
                "metadata": {"bill_id": 1, "amount": 1500000}
            }
        }

class NotificationResponse(NotificationBase):
    """Notification response schema"""
    id: int
    user_id: int
    user: Optional[UserResponse] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# System configuration schemas
class SystemConfigBase(BaseModel):
    """Base system configuration schema"""
    key: str
    value: str
    description: Optional[str] = None
    is_public: bool = False
    
    class Config:
        from_attributes = True

class SystemConfigCreate(SystemConfigBase):
    """System configuration creation schema"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "maintenance_mode",
                "value": "false",
                "description": "Enable/disable maintenance mode",
                "is_public": True
            }
        }

class SystemConfigUpdate(BaseModel):
    """System configuration update schema"""
    value: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "value": "true",
                "description": "System is under maintenance"
            }
        }

class SystemConfigResponse(SystemConfigBase):
    """System configuration response schema"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    
    class Config:
        from_attributes = True

# Report schemas
class ReportRequest(BaseModel):
    """Report request schema"""
    report_type: str
    start_date: datetime
    end_date: datetime
    agent_id: Optional[int] = None
    group_by: str = "day"
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_type": "sales",
                "start_date": "2023-12-01T00:00:00",
                "end_date": "2023-12-31T23:59:59",
                "agent_id": 1,
                "group_by": "day"
            }
        }

class ReportResponse(BaseModel):
    """Report response schema"""
    success: bool = True
    report_type: str
    start_date: datetime
    end_date: datetime
    data: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

# Import/Export schemas
class ImportRequest(BaseModel):
    """Import request schema"""
    import_type: str
    file_format: str = "csv"
    overwrite: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "import_type": "bills",
                "file_format": "csv",
                "overwrite": False
            }
        }

class ExportRequest(BaseModel):
    """Export request schema"""
    export_type: str
    format: str = "csv"
    filters: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "export_type": "transactions",
                "format": "excel",
                "filters": {"start_date": "2023-12-01", "end_date": "2023-12-31"}
            }
        }

# Search schemas
class SearchRequest(BaseModel):
    """Search request schema"""
    query: str = Field(..., min_length=2)
    search_type: str = "all"
    limit: int = Field(10, ge=1, le=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "john",
                "search_type": "users",
                "limit": 10
            }
        }

class SearchResponse(BaseModel):
    """Search response schema"""
    success: bool = True
    query: str
    search_type: str
    results: Dict[str, List[Any]]
    total_results: int
    
    class Config:
        from_attributes = True

# Dashboard schemas
class DashboardStats(BaseModel):
    """Dashboard statistics schema"""
    total_users: int
    total_agents: int
    total_customers: int
    total_bills: int
    total_transactions: int
    total_revenue: Decimal
    pending_bills: int
    active_agents: int
    recent_activities: List[ActivityLogResponse]
    
    class Config:
        from_attributes = True

# File upload schemas
class FileUploadResponse(BaseModel):
    """File upload response schema"""
    success: bool = True
    filename: str
    file_url: str
    file_size: int
    content_type: str
    message: str = "File uploaded successfully"
    
    class Config:
        from_attributes = True

# Health check schemas
class HealthCheckResponse(BaseModel):
    """Health check response schema"""
    status: str
    service: str
    timestamp: datetime
    features: Dict[str, bool]
    dependencies: Optional[Dict[str, str]] = None
    
    class Config:
        from_attributes = True

# Audit log schemas
class AuditLogRequest(BaseModel):
    """Audit log request schema"""
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "user_created",
                "resource_type": "user",
                "resource_id": 1,
                "details": "Created new user account"
            }
        }

# Webhook schemas
class WebhookPayload(BaseModel):
    """Webhook payload schema"""
    event: str
    data: Dict[str, Any]
    timestamp: datetime
    signature: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "event": "payment.received",
                "data": {"transaction_id": 1, "amount": 1500000},
                "timestamp": "2023-12-31T23:59:59",
                "signature": "abc123..."
            }
        }

# API key schemas
class APIKeyCreate(BaseModel):
    """API key creation schema"""
    name: str
    permissions: List[str] = []
    expires_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Mobile App API Key",
                "permissions": ["bills:read", "transactions:create"],
                "expires_at": "2024-12-31T23:59:59"
            }
        }

class APIKeyResponse(BaseModel):
    """API key response schema"""
    id: int
    name: str
    key: str
    secret: Optional[str] = None  # Only shown on creation
    permissions: List[str]
    user_id: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Password validation schemas
class PasswordValidationResponse(BaseModel):
    """Password validation response schema"""
    is_valid: bool
    errors: List[str] = []
    suggestions: List[str] = []
    
    class Config:
        from_attributes = True

# Bulk operation schemas
class BulkOperationRequest(BaseModel):
    """Bulk operation request schema"""
    operation: str
    data: List[Dict[str, Any]]
    batch_size: int = Field(100, ge=1, le=1000)
    dry_run: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "operation": "create",
                "data": [{"username": "user1", "email": "user1@example.com"}],
                "batch_size": 100,
                "dry_run": True
            }
        }

class BulkOperationResponse(BaseModel):
    """Bulk operation response schema"""
    success: bool
    operation: str
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    errors: List[Dict[str, Any]] = []
    results: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True

# Schedule schemas
class ScheduleCreate(BaseModel):
    """Schedule creation schema"""
    name: str
    schedule_type: str
    cron_expression: str
    task_name: str
    task_params: Dict[str, Any]
    is_active: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Daily Backup",
                "schedule_type": "cron",
                "cron_expression": "0 2 * * *",
                "task_name": "backup_database",
                "task_params": {"backup_type": "full"},
                "is_active": True
            }
        }

# Backup schemas
class BackupRequest(BaseModel):
    """Backup request schema"""
    backup_type: str = "full"
    include_data: bool = True
    include_schema: bool = True
    compress: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "backup_type": "full",
                "include_data": True,
                "include_schema": True,
                "compress": True
            }
        }

class BackupResponse(BaseModel):
    """Backup response schema"""
    success: bool
    backup_id: str
    filename: str
    file_size: int
    backup_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============ MISSING SCHEMAS ADDED ============

# Common/Pagination schemas
class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
    
    class Config:
        from_attributes = True

class DateRange(BaseModel):
    """Date range filter"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Dashboard schemas
class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_agents: int = 0
    total_customers: int = 0
    total_bills: int = 0
    total_transactions: int = 0
    today_revenue: float = 0.0
    today_transactions: int = 0
    pending_agents: int = 0
    pending_bills: int = 0
    overdue_bills: int = 0
    agent_trend: Optional[dict] = None
    bill_trend: Optional[dict] = None
    revenue_trend: Optional[dict] = None
    transaction_trend: Optional[dict] = None

class SalesChartData(BaseModel):
    """Sales chart data"""
    date: str
    amount: Decimal
    count: int

class BillsChartData(BaseModel):
    """Bills chart data"""
    status: str
    count: int
    amount: Decimal

class RecentActivity(BaseModel):
    """Recent activity item"""
    id: int
    type: str
    description: str
    timestamp: datetime
    user_id: Optional[int] = None
    user_name: Optional[str] = None

class TopAgent(BaseModel):
    """Top performing agent"""
    id: int
    full_name: str
    agent_code: Optional[str] = None
    total_sales: float = 0.0
    bill_count: int = 0
    success_rate: float = 0.0

class DashboardResponse(BaseModel):
    """Dashboard response schema"""
    stats: DashboardStats
    sales_data: List[SalesChartData] = []
    bills_data: List[BillsChartData] = []
    recent_activities: List[RecentActivity] = []
    top_agents: List[TopAgent] = []
    
    class Config:
        from_attributes = True

# Report schemas
class SalesReportItem(BaseModel):
    """Sales report item"""
    date: str
    amount: Decimal
    count: int
    agent_id: Optional[int] = None
    agent_name: Optional[str] = None

class AgentReportItem(BaseModel):
    """Agent report item"""
    agent_id: int
    agent_name: str
    total_bills: int = 0
    total_revenue: Decimal = Decimal('0.00')
    commission: Decimal = Decimal('0.00')
    approval_rate: float = 0.0

class SystemReportItem(BaseModel):
    """System report item"""
    date: str
    total_transactions: int = 0
    total_revenue: Decimal = Decimal('0.00')
    total_users: int = 0
    total_agents: int = 0

class ReportRequest(BaseModel):
    """Report request schema"""
    report_type: str  # 'sales', 'agent', 'system'
    start_date: datetime
    end_date: datetime
    include_details: bool = False
    format: str = 'json'  # 'json', 'csv', 'excel'

class ReportResponse(BaseModel):
    """Report response schema"""
    report_type: str
    data: List[Any] = []
    summary: Dict[str, Any] = {}
    generated_at: datetime
    
    class Config:
        from_attributes = True

# Transaction schemas
class TransactionFilter(BaseModel):
    """Transaction filter"""
    transaction_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    agent_id: Optional[int] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None

class TransactionStatsResponse(BaseModel):
    """Transaction statistics response"""
    total_count: int = 0
    total_amount: Decimal = Decimal('0.00')
    by_type: Dict[str, Any] = {}
    by_status: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True

# Bill schemas
class BillImportRequest(BaseModel):
    """Bill import request"""
    file_name: str
    file_path: str
    import_type: str = 'new'  # 'new', 'update'
    duplicate_action: str = 'skip'  # 'skip', 'update', 'error'

class BillImportResponse(BaseModel):
    """Bill import response"""
    success: bool
    total_imported: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    errors: List[str] = []
    
    class Config:
        from_attributes = True

# Customer schemas
class CustomerStats(BaseModel):
    """Customer statistics"""
    total_bills: int = 0
    total_paid: Decimal = Decimal('0.00')
    total_pending: Decimal = Decimal('0.00')
    last_transaction_date: Optional[datetime] = None

class CustomerSearchResponse(BaseModel):
    """Customer search response"""
    id: int
    customer_code: str
    customer_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True

# System schemas
class SystemConfigResponse(BaseModel):
    """System configuration response"""
    config_key: str
    config_value: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class SystemConfigUpdate(BaseModel):
    """System configuration update"""
    config_value: str

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str  # 'healthy', 'degraded', 'offline'
    timestamp: datetime
    database: str = 'ok'
    cache: str = 'ok'
    details: Dict[str, Any] = {}

class ImportResponse(BaseModel):
    """Import response"""
    success: bool
    total_imported: int = 0
    total_failed: int = 0
    errors: List[str] = []

class ApiSystemStatus(BaseModel):
    """API system status"""
    status: str
    uptime: int
    version: str
    timestamp: datetime

# External API schemas
class ApiBillResponse(BaseModel):
    """Bill response for external API"""
    bill_id: int
    bill_code: str
    customer_id: int
    amount: Decimal
    status: str
    due_date: Optional[date] = None

class ApiBillPaymentRequest(BaseModel):
    """Bill payment request for external API"""
    bill_id: int
    amount: Decimal
    payment_method: str = 'bank_transfer'

class ApiBillPaymentResponse(BaseModel):
    """Bill payment response for external API"""
    success: bool
    transaction_id: str
    bill_id: int
    amount: Decimal
    payment_date: datetime

class ApiBalanceResponse(BaseModel):
    """Balance response for external API"""
    agent_id: int
    current_balance: Decimal
    available_balance: Decimal
    total_commission: Decimal
    pending_withdrawal: Decimal

class ApiTransactionResponse(BaseModel):
    """Transaction response for external API"""
    transaction_id: int
    type: str
    amount: Decimal
    status: str
    created_at: datetime
    description: Optional[str] = None

class ApiTopUpRequest(BaseModel):
    """Top-up request for external API"""
    agent_id: int
    amount: Decimal
    payment_method: str = 'bank_transfer'
    reference: Optional[str] = None

class ApiTopUpResponse(BaseModel):
    """Top-up response for external API"""
    success: bool
    transaction_id: str
    agent_id: int
    amount: Decimal
    new_balance: Decimal
    timestamp: datetime

class ApiCheckBillRequest(BaseModel):
    """Check bill request for external API"""
    bill_code: str

class ApiCheckBillResponse(BaseModel):
    """Check bill response for external API"""
    found: bool
    bill: Optional[ApiBillResponse] = None
    message: Optional[str] = None

class ApiWebhookConfig(BaseModel):
    """Webhook configuration for external API"""
    webhook_url: str
    events: List[str] = []
    is_active: bool = True
    secret_key: Optional[str] = None

class ApiAgentInfoResponse(BaseModel):
    """Agent information response for external API"""
    agent_id: int
    agent_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str
    commission_rate: Decimal = Decimal('0.00')

# Deposit/Wallet schemas
class DepositRequest(BaseModel):
    """Request schema for agent deposit"""
    amount: Decimal = Field(..., gt=0, decimal_places=0)
    payment_method: str = Field("cash", min_length=1, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "amount": 5000000,
                "payment_method": "bank_transfer",
                "notes": "Nạp tiền tháng 12"
            }
        }

class DepositResponse(BaseModel):
    """Response schema for deposit transaction"""
    id: int
    transaction_code: str
    agent_id: int
    amount: Decimal
    fee: Decimal
    total_amount: Decimal
    payment_method: str
    status: str
    previous_balance: Decimal
    new_balance: Decimal
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class AgentWalletResponse(BaseModel):
    """Agent wallet/balance response"""
    agent_id: int
    agent_name: str
    current_balance: Decimal
    frozen_balance: Decimal
    available_balance: Decimal
    total_deposit: Decimal
    total_withdraw: Decimal
    total_sales: Decimal
    total_commission: Decimal
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DepositHistoryResponse(BaseModel):
    """Deposit history item"""
    id: int
    transaction_code: str
    amount: Decimal
    fee: Decimal
    total_amount: Decimal
    payment_method: str
    status: str
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
