from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    ForeignKey, Text, JSON, Enum, Numeric, BigInteger,
    Date, Time, Index, UniqueConstraint, CheckConstraint,
    func, text, DECIMAL, LargeBinary
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import enum
from datetime import datetime, date, timedelta
import re
from typing import Optional, Dict, Any, List

from database import Base
from security import verify_password, get_password_hash  # Changed import

# Enums
class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    AGENT = "AGENT"
    STAFF = "STAFF"
    VIEWER = "VIEWER"
    CUSTOMER = "CUSTOMER"

class AgentType(str, enum.Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"

class AgentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"

class BillStatus(str, enum.Enum):
    IN_STOCK = "in_stock"      # Hóa đơn trong kho
    SOLD = "sold"              # Đã bán cho đại lý
    PAID = "paid"              # Đã thanh toán
    PENDING = "pending"        # Chờ xử lý
    CANCELLED = "cancelled"    # Đã hủy
    EXPIRED = "expired"        # Hết hạn

class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"        # Nạp tiền
    WITHDRAW = "withdraw"      # Rút tiền
    BILL_PAYMENT = "bill_payment"  # Thanh toán hóa đơn
    COMMISSION = "commission"  # Hoa hồng
    REFUND = "refund"          # Hoàn tiền
    TRANSFER = "transfer"      # Chuyển khoản

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PROCESSING = "processing"

class NotificationType(str, enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SYSTEM = "system"

class NotificationStatus(str, enum.Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

class ActivityType(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"
    PAYMENT = "payment"

# Module Types - Các module trong hệ thống
class ModuleType(str, enum.Enum):
    # Admin modules
    DASHBOARD = "dashboard"           # Trang Dashboard
    AGENTS = "agents"                 # Quản lý Đại lý
    BILLS = "bills"                   # Quản lý Hóa đơn
    TRANSACTIONS = "transactions"     # Quản lý Giao dịch
    CUSTOMERS = "customers"           # Quản lý Khách hàng THẺ
    USERS = "users"                   # Quản lý Người dùng
    REPORTS = "reports"               # Báo cáo
    API_WEBHOOKS = "api_webhooks"     # API & Webhooks
    SETTINGS = "settings"             # Cài đặt hệ thống
    
    # Role-based access
    ADMIN_PORTAL = "admin_portal"     # Cổng Quản trị Web
    AGENT_PORTAL = "agent_portal"     # Cổng Đại lý
    STAFF_PORTAL = "staff_portal"     # Cổng Nhân viên
    CUSTOMER_PORTAL = "customer_portal"  # Cổng Khách hàng THẺ

# Permission Types - Các quyền trên mỗi module
class PermissionType(str, enum.Enum):
    VIEW = "view"           # Xem
    CREATE = "create"       # Tạo mới
    EDIT = "edit"           # Chỉnh sửa
    DELETE = "delete"       # Xóa
    EXPORT = "export"       # Xuất dữ liệu
    IMPORT = "import"       # Nhập dữ liệu
    APPROVE = "approve"     # Duyệt
    FULL = "full"           # Toàn quyền

# Base Mixin for common fields
class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

# User Model
class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    phone = Column(String(20), index=True, nullable=True)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.AGENT, nullable=False)
    
    # Profile fields
    avatar_url = Column(String(500), nullable=True)
    identity_card = Column(String(20), nullable=True, index=True)  # CMND/CCCD
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)  # male, female, other
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    
    # CCCD Images
    cccd_front = Column(String(500), nullable=True)  # Path to front image
    cccd_back = Column(String(500), nullable=True)   # Path to back image
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Multi-role flags (1 user can have multiple roles)
    is_staff = Column(Boolean, default=False, nullable=False)  # Nhân viên
    
    # Security
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    
    # 2FA
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(100), nullable=True)
    
    # API Access
    api_key = Column(String(100), unique=True, nullable=True)
    api_secret = Column(String(255), nullable=True)
    api_calls_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    agent = relationship("Agent", back_populates="user", uselist=False, foreign_keys="Agent.user_id")
    activities = relationship("ActivityLog", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    created_bills = relationship("Bill", foreign_keys="Bill.created_by_id", back_populates="creator")
    transactions = relationship("Transaction", back_populates="user")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_role_status', 'role', 'is_active'),
        Index('idx_user_phone', 'phone'),
        Index('idx_user_created', 'created_at'),
    )
    
    @validates('email')
    def validate_email(self, key, email):
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            raise ValueError("Invalid email format")
        return email
    
    @validates('phone')
    def validate_phone(self, key, phone):
        if phone and not re.match(r'^\+?[0-9\s\-\(\)]{10,}$', phone):
            raise ValueError("Invalid phone number format")
        return phone
    
    @hybrid_property
    def is_locked(self):
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def verify_password(self, password: str) -> bool:
        return verify_password(password, self.password_hash)
    
    def set_password(self, password: str):
        try:
            self.password_hash = get_password_hash(password)
        except ValueError as e:
            if "72" in str(e):
                # Force truncate and retry
                truncated_pwd = password[:72]
                self.password_hash = get_password_hash(truncated_pwd)
            else:
                raise
    
    def get_initial_avatar(self) -> str:
        """Generate initials for avatar"""
        names = self.full_name.split()
        if len(names) >= 2:
            return (names[0][0] + names[-1][0]).upper()
        elif len(self.full_name) >= 2:
            return self.full_name[:2].upper()
        else:
            return "U"

# Agent Model
class Agent(Base, TimestampMixin):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    agent_code = Column(String(50), unique=True, index=True, nullable=False)
    agent_name = Column(String(100), nullable=False)  # Tên Đại Lý
    company_name = Column(String(200), nullable=True)
    tax_code = Column(String(20), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    agent_type = Column(Enum(AgentType), default=AgentType.INDIVIDUAL, nullable=False)
    status = Column(Enum(AgentStatus), default=AgentStatus.PENDING, nullable=False)
    
    # Commission rates
    commission_rate = Column(Numeric(5, 2), default=0.0, nullable=False)  # Tỷ lệ hoa hồng
    min_commission = Column(Numeric(12, 0), default=0, nullable=False)     # Hoa hồng tối thiểu
    max_commission = Column(Numeric(12, 0), default=10000000, nullable=False)  # Hoa hồng tối đa
    
    # Financials
    balance = Column(Numeric(15, 0), default=0, nullable=False)           # Số dư khả dụng
    frozen_balance = Column(Numeric(15, 0), default=0, nullable=False)    # Số dư đóng băng
    total_deposit = Column(Numeric(15, 0), default=0, nullable=False)     # Tổng nạp
    total_withdraw = Column(Numeric(15, 0), default=0, nullable=False)    # Tổng rút
    total_sales = Column(Numeric(15, 0), default=0, nullable=False)       # Tổng doanh số
    total_commission = Column(Numeric(15, 0), default=0, nullable=False)  # Tổng hoa hồng
    
    # Limits
    daily_limit = Column(Numeric(15, 0), default=50000000, nullable=False)    # Giới hạn giao dịch/ngày
    per_transaction_limit = Column(Numeric(15, 0), default=10000000, nullable=False)  # Giới hạn/giao dịch
    
    # Statistics
    total_customers = Column(Integer, default=0, nullable=False)
    total_bills = Column(Integer, default=0, nullable=False)
    total_successful_bills = Column(Integer, default=0, nullable=False)
    success_rate = Column(Numeric(5, 2), default=0.0, nullable=False)  # Tỷ lệ thành công
    
    # Reward Points
    reward_points = Column(Integer, default=0, nullable=False)          # Điểm thưởng hiện tại
    total_points_earned = Column(Integer, default=0, nullable=False)    # Tổng điểm đã kiếm
    total_points_redeemed = Column(Integer, default=0, nullable=False)  # Tổng điểm đã đổi
    vip_tier = Column(String(20), default="bronze")                     # bronze, silver, gold, platinum, diamond
    
    # Approval
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Store Info
    store_address = Column(String(500), nullable=True)
    
    # Document Images
    cccd_front_path = Column(String(500), nullable=True)
    cccd_back_path = Column(String(500), nullable=True)
    store_image_1_path = Column(String(500), nullable=True)
    store_image_2_path = Column(String(500), nullable=True)
    store_image_3_path = Column(String(500), nullable=True)
    
    # Audit
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="agent", foreign_keys=[user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    customers = relationship("Customer", back_populates="agent")
    bills = relationship("Bill", back_populates="agent")
    transactions = relationship("Transaction", back_populates="agent")
    commission_logs = relationship("CommissionLog", back_populates="agent")
    reward_transactions = relationship("RewardTransaction", back_populates="agent")
    
    # Indexes
    __table_args__ = (
        Index('idx_agent_code', 'agent_code'),
        Index('idx_agent_status', 'status'),
        Index('idx_agent_type', 'agent_type'),
        Index('idx_agent_balance', 'balance'),
        UniqueConstraint('user_id', name='uq_agent_user'),
    )
    
    @hybrid_property
    def available_balance(self):
        return self.balance - self.frozen_balance
    
    @hybrid_property
    def is_approved(self):
        return self.status == AgentStatus.ACTIVE and self.approved_at is not None
    
    def can_process_transaction(self, amount: float) -> bool:
        """Check if agent can process transaction"""
        if self.status != AgentStatus.ACTIVE:
            return False
        if amount > self.available_balance:
            return False
        if amount > self.per_transaction_limit:
            return False
        return True
    
    def get_today_transactions_total(self, db) -> float:
        """Get total transactions for today"""
        from sqlalchemy import func, Date
        from datetime import date
        
        today = date.today()
        result = db.query(func.sum(Transaction.amount)).filter(
            Transaction.agent_id == self.id,
            Transaction.status == TransactionStatus.COMPLETED,
            func.date(Transaction.created_at) == today
        ).scalar()
        
        return result or 0.0

# Customer Model
class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_code = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), index=True, nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(String(500), nullable=False)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    
    # User relationship - liên kết tài khoản
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    
    # Credit card information - Thông tin thẻ tín dụng
    bank_name = Column(String(50), nullable=True)           # Ngân hàng phát hành (VCB, TCB, VPB...)
    card_type = Column(String(30), nullable=True)           # Loại thẻ (visa, mastercard, jcb, amex, napas)
    card_last_digits = Column(String(19), nullable=True)    # Số thẻ 16 số (với khoảng trắng: XXXX XXXX XXXX XXXX)
    card_cvv = Column(String(4), nullable=True)             # Mã CVV/CVC (3-4 số)
    card_expiry = Column(String(5), nullable=True)          # Ngày hết hạn (MM/YY)
    card_holder_name = Column(String(100), nullable=True)   # Tên in trên thẻ
    card_tier = Column(String(20), nullable=True)           # Hạng thẻ (standard, gold, platinum, signature, infinite)
    issue_date = Column(Date, nullable=True)                # Ngày phát hành thẻ
    billing_cycle = Column(Integer, nullable=True)          # Chu kỳ sao kê (ngày trong tháng)
    credit_limit = Column(Numeric(15, 0), nullable=True)    # Hạn mức thẻ
    
    # Customer type
    customer_type = Column(String(20), default='individual', nullable=True)  # individual, business, organization
    
    # Agent relationship
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    
    # Statistics
    total_bills = Column(Integer, default=0, nullable=False)
    total_paid = Column(Numeric(15, 0), default=0, nullable=False)
    avg_bill_amount = Column(Numeric(12, 0), default=0, nullable=False)
    last_payment_date = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", backref="customer_profile")
    agent = relationship("Agent", back_populates="customers")
    bills = relationship("Bill", back_populates="customer")
    
    # Indexes
    __table_args__ = (
        Index('idx_customer_agent', 'agent_id'),
        Index('idx_customer_bank', 'bank_name'),
        Index('idx_customer_city', 'city'),
        Index('idx_customer_user', 'user_id'),
    )
    
    @validates('email')
    def validate_email(self, key, email):
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            raise ValueError("Invalid email format")
        return email

# Bill Model
class Bill(Base, TimestampMixin):
    __tablename__ = "bills"
    
    id = Column(Integer, primary_key=True, index=True)
    bill_code = Column(String(50), unique=True, index=True, nullable=False)
    
    # Customer information
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_code = Column(String(20), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_address = Column(String(500), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    
    # Electricity information
    evn_customer_code = Column(String(50), nullable=True)
    period = Column(String(7), nullable=False)  # Format: YYYY-MM
    due_date = Column(Date, nullable=True)
    
    # Amounts
    total_amount = Column(Numeric(15, 0), nullable=False)          # Tổng tiền
    electricity_amount = Column(Numeric(15, 0), nullable=False)    # Tiền điện
    vat_amount = Column(Numeric(15, 0), default=0, nullable=False) # VAT
    other_fees = Column(Numeric(15, 0), default=0, nullable=False) # Phí khác
    
    # Consumption
    consumption = Column(Numeric(10, 2), nullable=True)            # Sản lượng kWh
    previous_index = Column(Numeric(10, 2), nullable=True)         # Chỉ số cũ
    current_index = Column(Numeric(10, 2), nullable=True)          # Chỉ số mới
    
    # Agent information
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    agent_commission = Column(Numeric(15, 0), default=0, nullable=False)  # Hoa hồng đại lý
    
    # Status
    status = Column(Enum(BillStatus), default=BillStatus.IN_STOCK, nullable=False)
    payment_date = Column(DateTime, nullable=True)
    
    # System information
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    imported_file = Column(String(255), nullable=True)
    imported_at = Column(DateTime, nullable=True)
    
    # Metadata - CHANGED FROM 'metadata' TO 'bill_metadata' TO AVOID CONFLICT
    evn_bill_code = Column(String(50), nullable=True)  # Mã hóa đơn EVN
    payment_method = Column(String(50), nullable=True)
    transaction_ref = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    bill_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata'
    
    # Relationships
    customer = relationship("Customer", back_populates="bills")
    agent = relationship("Agent", back_populates="bills")
    creator = relationship("User", foreign_keys=[created_by_id], back_populates="created_bills")
    transactions = relationship("Transaction", back_populates="bill")
    
    # Indexes
    __table_args__ = (
        Index('idx_bill_code', 'bill_code'),
        Index('idx_bill_status', 'status'),
        Index('idx_bill_period', 'period'),
        Index('idx_bill_agent', 'agent_id'),
        Index('idx_bill_customer', 'customer_code'),
        Index('idx_bill_created', 'created_at'),
        Index('idx_bill_payment_date', 'payment_date'),
    )
    
    @hybrid_property
    def is_overdue(self):
        if self.due_date and self.status in [BillStatus.IN_STOCK, BillStatus.PENDING]:
            return self.due_date < date.today()
        return False
    
    @hybrid_property
    def days_overdue(self):
        if self.is_overdue:
            return (date.today() - self.due_date).days
        return 0

# Transaction Model
class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_code = Column(String(50), unique=True, index=True, nullable=False)
    
    # Transaction details
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True)
    
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(15, 0), nullable=False)
    fee = Column(Numeric(15, 0), default=0, nullable=False)
    total_amount = Column(Numeric(15, 0), nullable=False)  # amount + fee
    
    # Status
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Payment information
    payment_method = Column(String(50), nullable=True)
    payment_gateway = Column(String(50), nullable=True)
    gateway_transaction_id = Column(String(100), nullable=True)
    gateway_response = Column(JSON, nullable=True)
    
    # Account balances
    previous_balance = Column(Numeric(15, 0), nullable=True)
    new_balance = Column(Numeric(15, 0), nullable=True)
    
    # Additional info
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    transaction_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata'
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    agent = relationship("Agent", back_populates="transactions")
    bill = relationship("Bill", back_populates="transactions")
    
    # Indexes
    __table_args__ = (
        Index('idx_transaction_code', 'transaction_code'),
        Index('idx_transaction_type', 'transaction_type'),
        Index('idx_transaction_status', 'status'),
        Index('idx_transaction_user', 'user_id'),
        Index('idx_transaction_agent', 'agent_id'),
        Index('idx_transaction_date', 'created_at'),
    )
    
    @hybrid_property
    def net_amount(self):
        """Amount after fee"""
        return self.amount - self.fee

# Commission Log Model
class CommissionLog(Base, TimestampMixin):
    __tablename__ = "commission_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    
    # Commission calculation
    bill_amount = Column(Numeric(15, 0), nullable=False)
    commission_rate = Column(Numeric(5, 2), nullable=False)
    commission_amount = Column(Numeric(15, 0), nullable=False)
    calculated_at = Column(DateTime, nullable=False)
    
    # Payment status
    is_paid = Column(Boolean, default=False, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    payment_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="commission_logs")
    bill = relationship("Bill")
    payment_transaction = relationship("Transaction")
    
    # Indexes
    __table_args__ = (
        Index('idx_commission_agent', 'agent_id'),
        Index('idx_commission_paid', 'is_paid'),
        Index('idx_commission_date', 'calculated_at'),
    )

# Notification Model
class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Notification content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(Enum(NotificationType), default=NotificationType.INFO, nullable=False)
    
    # Metadata
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    action_url = Column(String(500), nullable=True)
    icon = Column(String(100), nullable=True)
    priority = Column(Integer, default=0, nullable=False)  # 0: low, 1: normal, 2: high
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index('idx_notification_user', 'user_id'),
        Index('idx_notification_read', 'is_read'),
        Index('idx_notification_created', 'created_at'),
    )

# Activity Log Model
class ActivityLog(Base, TimestampMixin):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Activity details
    activity_type = Column(Enum(ActivityType), nullable=False)
    action = Column(String(200), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Resource information
    resource_type = Column(String(50), nullable=True)  # e.g., 'agent', 'bill', 'transaction'
    resource_id = Column(Integer, nullable=True)
    resource_changes = Column(JSON, nullable=True)  # Store changes made
    
    # Relationships
    user = relationship("User", back_populates="activities")
    
    # Indexes
    __table_args__ = (
        Index('idx_activity_user', 'user_id'),
        Index('idx_activity_type', 'activity_type'),
        Index('idx_activity_date', 'created_at'),
        Index('idx_activity_resource', 'resource_type', 'resource_id'),
    )

# System Configuration Model
class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), nullable=False)  # string, integer, float, boolean, json
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    updated_by = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_config_key', 'key'),
        Index('idx_config_category', 'category'),
    )

# API Log Model
class ApiLog(Base, TimestampMixin):
    __tablename__ = "api_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    
    # Request details
    method = Column(String(10), nullable=False)
    endpoint = Column(String(500), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Request/Response
    request_headers = Column(JSON, nullable=True)
    request_body = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=False)
    response_body = Column(Text, nullable=True)
    
    # Performance
    response_time = Column(Numeric(10, 4), nullable=False)  # in seconds
    
    # Relationships
    user = relationship("User")
    agent = relationship("Agent")
    
    # Indexes
    __table_args__ = (
        Index('idx_api_log_endpoint', 'endpoint'),
        Index('idx_api_log_status', 'response_status'),
        Index('idx_api_log_date', 'created_at'),
        Index('idx_api_log_user', 'user_id'),
    )

# File Upload Model
class UploadedFile(Base, TimestampMixin):
    __tablename__ = "uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    mime_type = Column(String(100), nullable=False)
    
    # Upload details
    upload_type = Column(String(50), nullable=False)  # bill_import, avatar, document, etc.
    status = Column(String(20), default="pending", nullable=False)
    
    # Processing info
    processed_at = Column(DateTime, nullable=True)
    processed_count = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)
    error_log = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_upload_user', 'user_id'),
        Index('idx_upload_type', 'upload_type'),
        Index('idx_upload_date', 'created_at'),
    )

# Backup Log Model
class BackupLog(Base, TimestampMixin):
    __tablename__ = "backup_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Backup details
    backup_type = Column(String(50), nullable=False)  # database, files, full
    backup_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # in bytes
    checksum = Column(String(64), nullable=True)
    
    # Status
    status = Column(String(20), nullable=False)  # success, failed, partial
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata - CHANGED FROM 'metadata' TO 'backup_metadata' TO AVOID CONFLICT
    backup_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata'
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_backup_date', 'created_at'),
        Index('idx_backup_status', 'status'),
        Index('idx_backup_type', 'backup_type'),
    )

# Audit Log Model
class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Audit details
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_table', 'table_name'),
        Index('idx_audit_record', 'table_name', 'record_id'),
        Index('idx_audit_date', 'created_at'),
        Index('idx_audit_user', 'user_id'),
    )

# File Upload Model
class FileUpload(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "file_uploads"
    
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, unique=True)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=True)
    upload_type = Column(String(50), nullable=False)  # 'bill_import', 'backup', 'export', etc
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User")


# User Permission Model - Quản lý quyền truy cập module
class UserPermission(Base, TimestampMixin):
    __tablename__ = "user_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    module = Column(Enum(ModuleType), nullable=False)
    permission = Column(Enum(PermissionType), default=PermissionType.VIEW, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit
    granted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Quyền có thời hạn
    notes = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="permissions")
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_permission_user', 'user_id'),
        Index('idx_permission_module', 'module'),
        Index('idx_permission_user_module', 'user_id', 'module'),
        UniqueConstraint('user_id', 'module', 'permission', name='uq_user_module_permission'),
    )
    
    @classmethod
    def has_permission(cls, db, user_id: int, module: ModuleType, permission: PermissionType = PermissionType.VIEW) -> bool:
        """Check if user has specific permission on a module"""
        perm = db.query(cls).filter(
            cls.user_id == user_id,
            cls.module == module,
            cls.is_active == True,
            (cls.expires_at == None) | (cls.expires_at > datetime.utcnow())
        ).first()
        
        if not perm:
            return False
        
        # FULL permission includes all others
        if perm.permission == PermissionType.FULL:
            return True
        
        return perm.permission == permission
    
    @classmethod
    def get_user_modules(cls, db, user_id: int) -> list:
        """Get all active modules for a user"""
        perms = db.query(cls).filter(
            cls.user_id == user_id,
            cls.is_active == True,
            (cls.expires_at == None) | (cls.expires_at > datetime.utcnow())
        ).all()
        return list(set([p.module for p in perms]))
    
    @classmethod
    def grant_default_permissions(cls, db, user_id: int, role: UserRole, granted_by_id: int = None):
        """Grant default permissions based on role"""
        default_perms = {
            UserRole.ADMIN: [
                (ModuleType.ADMIN_PORTAL, PermissionType.FULL),
                (ModuleType.DASHBOARD, PermissionType.FULL),
                (ModuleType.AGENTS, PermissionType.FULL),
                (ModuleType.BILLS, PermissionType.FULL),
                (ModuleType.TRANSACTIONS, PermissionType.FULL),
                (ModuleType.CUSTOMERS, PermissionType.FULL),
                (ModuleType.USERS, PermissionType.FULL),
                (ModuleType.REPORTS, PermissionType.FULL),
                (ModuleType.API_WEBHOOKS, PermissionType.FULL),
                (ModuleType.SETTINGS, PermissionType.FULL),
            ],
            UserRole.MANAGER: [
                (ModuleType.ADMIN_PORTAL, PermissionType.VIEW),
                (ModuleType.DASHBOARD, PermissionType.VIEW),
                (ModuleType.AGENTS, PermissionType.FULL),
                (ModuleType.BILLS, PermissionType.FULL),
                (ModuleType.TRANSACTIONS, PermissionType.VIEW),
                (ModuleType.CUSTOMERS, PermissionType.FULL),
                (ModuleType.REPORTS, PermissionType.VIEW),
            ],
            UserRole.STAFF: [
                (ModuleType.STAFF_PORTAL, PermissionType.FULL),
                (ModuleType.DASHBOARD, PermissionType.VIEW),
                (ModuleType.BILLS, PermissionType.EDIT),
                (ModuleType.TRANSACTIONS, PermissionType.VIEW),
                (ModuleType.CUSTOMERS, PermissionType.VIEW),
            ],
            UserRole.AGENT: [
                (ModuleType.AGENT_PORTAL, PermissionType.FULL),
                (ModuleType.BILLS, PermissionType.VIEW),
                (ModuleType.TRANSACTIONS, PermissionType.VIEW),
            ],
            UserRole.VIEWER: [
                (ModuleType.DASHBOARD, PermissionType.VIEW),
                (ModuleType.REPORTS, PermissionType.VIEW),
            ],
        }
        
        perms_to_grant = default_perms.get(role, [])
        for module, permission in perms_to_grant:
            existing = db.query(cls).filter(
                cls.user_id == user_id,
                cls.module == module,
                cls.permission == permission
            ).first()
            
            if not existing:
                new_perm = cls(
                    user_id=user_id,
                    module=module,
                    permission=permission,
                    granted_by_id=granted_by_id,
                    is_active=True
                )
                db.add(new_perm)
        
        db.commit()


# ==================== REWARD POINTS SYSTEM ====================

class RewardProgramType(str, enum.Enum):
    """Loại chương trình thưởng"""
    REGISTRATION = "registration"           # Thưởng đăng ký mới
    FIRST_DEPOSIT = "first_deposit"         # Thưởng nạp tiền lần đầu
    DEPOSIT_BONUS = "deposit_bonus"         # Thưởng % nạp tiền
    TRANSACTION_BONUS = "transaction_bonus" # Thưởng giao dịch
    MONTHLY_SALES = "monthly_sales"         # Thưởng doanh số tháng
    REFERRAL = "referral"                   # Thưởng giới thiệu
    BIRTHDAY = "birthday"                   # Thưởng sinh nhật
    LOYALTY = "loyalty"                     # Thưởng trung thành
    HOLIDAY = "holiday"                     # Thưởng lễ hội
    VIP_TIER = "vip_tier"                   # Thưởng hạng VIP


class RewardProgram(Base):
    """Chương trình thưởng điểm"""
    __tablename__ = "reward_programs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic info
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    program_type = Column(Enum(RewardProgramType), nullable=False)
    
    # Reward configuration
    points_amount = Column(Integer, default=0)          # Số điểm cố định
    points_percentage = Column(DECIMAL(5, 2), default=0)  # % của giao dịch
    min_amount = Column(DECIMAL(15, 2), default=0)      # Số tiền tối thiểu để áp dụng
    max_points = Column(Integer, nullable=True)          # Điểm tối đa mỗi lần
    
    # Conditions
    min_transactions = Column(Integer, default=0)       # Số giao dịch tối thiểu
    min_deposit = Column(DECIMAL(15, 2), default=0)     # Nạp tối thiểu
    required_days = Column(Integer, default=0)          # Số ngày yêu cầu (loyalty)
    
    # Multiplier & limits
    multiplier = Column(DECIMAL(5, 2), default=1.0)     # Hệ số nhân
    daily_limit = Column(Integer, nullable=True)        # Giới hạn lần/ngày
    monthly_limit = Column(Integer, nullable=True)      # Giới hạn lần/tháng
    total_limit = Column(Integer, nullable=True)        # Tổng giới hạn
    
    # Status & scheduling
    is_active = Column(Boolean, default=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    # Metadata
    icon = Column(String(50), default="fas fa-gift")
    color = Column(String(20), default="#28a745")
    priority = Column(Integer, default=0)               # Thứ tự ưu tiên
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    reward_transactions = relationship("RewardTransaction", back_populates="program")
    
    def __repr__(self):
        return f"<RewardProgram {self.code}: {self.name}>"


class RewardTransaction(Base):
    """Giao dịch điểm thưởng của đại lý"""
    __tablename__ = "reward_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # References
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("reward_programs.id"), nullable=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    # Transaction details
    transaction_code = Column(String(50), unique=True, nullable=False, index=True)
    points = Column(Integer, nullable=False)            # Điểm (+/-)
    points_type = Column(String(20), default="earn")    # earn, redeem, expire, adjust
    
    # Balance tracking
    previous_balance = Column(Integer, default=0)
    new_balance = Column(Integer, default=0)
    
    # Description
    description = Column(Text, nullable=True)
    reference_type = Column(String(50), nullable=True)  # deposit, transaction, manual, etc.
    reference_id = Column(Integer, nullable=True)
    
    # Extra data
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="reward_transactions")
    program = relationship("RewardProgram", back_populates="reward_transactions")
    created_by = relationship("User", foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f"<RewardTransaction {self.transaction_code}: {self.points} points>"


# Add reward fields to Agent model - will be handled via migration or direct add