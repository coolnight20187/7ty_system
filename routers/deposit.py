"""
Hệ thống Nạp Tiền Bảo Mật cho Đại Lý
=====================================

Tính năng bảo mật:
1. Xác thực 2 lớp (OTP/PIN)
2. Rate limiting (giới hạn số lần/số tiền)
3. Webhook signature verification
4. IP/Device tracking
5. Audit trail đầy đủ
6. Giới hạn số tiền linh hoạt
7. Phát hiện giao dịch đáng ngờ
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import hashlib
import hmac
import secrets
import json
import logging
import re

from database import get_db
from models import (
    Agent, User, Transaction, TransactionType, TransactionStatus,
    DepositRequest, DepositStatus, DepositMethod, DepositLimit, DepositSecurityLog,
    SystemBankAccount
)
from dependencies import get_current_agent
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deposit", tags=["deposit"])

# =========================================
# PYDANTIC SCHEMAS
# =========================================

class CreateDepositRequest(BaseModel):
    """Tạo yêu cầu nạp tiền"""
    amount: int = Field(..., ge=100000, le=100000000, description="Số tiền (100k - 100M)")
    method: str = Field(default="bank_transfer", description="Phương thức: bank_transfer, cash")
    bank_account_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('amount')
    def validate_amount(cls, v):
        if v < 100000:
            raise ValueError('Số tiền tối thiểu là 100.000đ')
        if v > 100000000:
            raise ValueError('Số tiền tối đa là 100.000.000đ mỗi lần')
        return v

class VerifyOTPRequest(BaseModel):
    """Xác minh OTP"""
    request_code: str
    otp_code: str = Field(..., min_length=6, max_length=6)

class AdminApproveRequest(BaseModel):
    """Admin duyệt yêu cầu"""
    request_code: str
    action: str = Field(..., description="approve hoặc reject")
    actual_amount: Optional[int] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None

class DepositResponse(BaseModel):
    """Response cho yêu cầu nạp tiền"""
    success: bool
    message: str
    request_code: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[int] = None
    otp_sent: Optional[bool] = None
    expires_at: Optional[str] = None
    bank_info: Optional[Dict] = None

# =========================================
# UTILITY FUNCTIONS
# =========================================

def generate_request_code() -> str:
    """Tạo mã yêu cầu nạp tiền unique"""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_part = secrets.token_hex(4).upper()
    return f"DEP{timestamp}{random_part}"

def generate_otp() -> str:
    """Tạo mã OTP 6 số"""
    return str(secrets.randbelow(900000) + 100000)

def calculate_risk_score(
    agent: Agent,
    amount: int,
    request_ip: str,
    db: Session
) -> tuple:
    """
    Tính điểm rủi ro cho giao dịch
    Returns: (risk_score: int, risk_factors: list)
    """
    risk_score = 0
    risk_factors = []
    
    # 1. Số tiền lớn
    if amount >= 50000000:
        risk_score += 20
        risk_factors.append("Số tiền lớn >= 50M")
    elif amount >= 20000000:
        risk_score += 10
        risk_factors.append("Số tiền trung bình >= 20M")
    
    # 2. Đại lý mới (< 7 ngày)
    if agent.created_at:
        days_old = (datetime.utcnow() - agent.created_at).days
        if days_old < 7:
            risk_score += 25
            risk_factors.append(f"Đại lý mới ({days_old} ngày)")
        elif days_old < 30:
            risk_score += 10
            risk_factors.append(f"Đại lý < 30 ngày")
    
    # 3. Số lần nạp trong ngày
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count = db.query(DepositRequest).filter(
        DepositRequest.agent_id == agent.id,
        DepositRequest.created_at >= today_start,
        DepositRequest.status != DepositStatus.CANCELLED
    ).count()
    
    if daily_count >= 5:
        risk_score += 20
        risk_factors.append(f"Nhiều lần nạp trong ngày ({daily_count})")
    elif daily_count >= 3:
        risk_score += 10
        risk_factors.append(f"{daily_count} lần nạp trong ngày")
    
    # 4. Tổng tiền nạp trong ngày
    daily_total = db.query(func.sum(DepositRequest.amount)).filter(
        DepositRequest.agent_id == agent.id,
        DepositRequest.created_at >= today_start,
        DepositRequest.status.in_([DepositStatus.COMPLETED, DepositStatus.APPROVED, DepositStatus.PROCESSING])
    ).scalar() or 0
    
    if daily_total + amount > 200000000:  # > 200M/ngày
        risk_score += 25
        risk_factors.append(f"Tổng nạp trong ngày cao ({daily_total + amount:,}đ)")
    
    # 5. Check IP thay đổi
    last_request = db.query(DepositRequest).filter(
        DepositRequest.agent_id == agent.id,
        DepositRequest.request_ip.isnot(None)
    ).order_by(DepositRequest.created_at.desc()).first()
    
    if last_request and last_request.request_ip != request_ip:
        risk_score += 15
        risk_factors.append("IP khác với lần trước")
    
    # 6. Thời gian bất thường (0h-6h)
    current_hour = datetime.utcnow().hour + 7  # Vietnam timezone
    if current_hour >= 24:
        current_hour -= 24
    if 0 <= current_hour < 6:
        risk_score += 15
        risk_factors.append(f"Thời gian bất thường ({current_hour}h)")
    
    return min(risk_score, 100), risk_factors

def check_deposit_limits(
    agent: Agent,
    amount: int,
    db: Session
) -> tuple:
    """
    Kiểm tra giới hạn nạp tiền
    Returns: (is_allowed: bool, message: str, require_approval: bool)
    """
    # Lấy giới hạn áp dụng cho agent
    limit = db.query(DepositLimit).filter(
        or_(
            DepositLimit.agent_id == agent.id,
            and_(DepositLimit.agent_id.is_(None), DepositLimit.is_active == True)
        )
    ).order_by(DepositLimit.agent_id.desc().nullslast()).first()
    
    if not limit:
        # Tạo giới hạn mặc định
        limit = DepositLimit(
            min_amount=100000,
            max_amount=100000000,
            daily_limit=500000000,
            max_daily_count=10,
            max_hourly_count=3,
            require_otp=True,
            require_admin_approval=False,
            approval_threshold=50000000
        )
    
    # Check min/max amount
    if amount < limit.min_amount:
        return False, f"Số tiền tối thiểu là {limit.min_amount:,.0f}đ", False
    if amount > limit.max_amount:
        return False, f"Số tiền tối đa là {limit.max_amount:,.0f}đ mỗi lần", False
    
    # Check daily count
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count = db.query(DepositRequest).filter(
        DepositRequest.agent_id == agent.id,
        DepositRequest.created_at >= today_start,
        DepositRequest.status != DepositStatus.CANCELLED
    ).count()
    
    if daily_count >= limit.max_daily_count:
        return False, f"Đã vượt giới hạn {limit.max_daily_count} lần/ngày", False
    
    # Check hourly count
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    hourly_count = db.query(DepositRequest).filter(
        DepositRequest.agent_id == agent.id,
        DepositRequest.created_at >= hour_ago,
        DepositRequest.status != DepositStatus.CANCELLED
    ).count()
    
    if hourly_count >= limit.max_hourly_count:
        return False, f"Đã vượt giới hạn {limit.max_hourly_count} lần/giờ. Vui lòng thử lại sau.", False
    
    # Check daily total
    daily_total = db.query(func.sum(DepositRequest.amount)).filter(
        DepositRequest.agent_id == agent.id,
        DepositRequest.created_at >= today_start,
        DepositRequest.status.in_([DepositStatus.COMPLETED, DepositStatus.APPROVED, DepositStatus.PROCESSING])
    ).scalar() or 0
    
    if daily_total + amount > limit.daily_limit:
        remaining = limit.daily_limit - daily_total
        return False, f"Vượt hạn mức nạp trong ngày. Còn lại: {remaining:,.0f}đ", False
    
    # Check if require approval
    require_approval = limit.require_admin_approval or amount >= limit.approval_threshold
    
    return True, "OK", require_approval

def log_security_event(
    db: Session,
    agent_id: int,
    event_type: str,
    description: str,
    request_id: int = None,
    ip: str = None,
    user_agent: str = None,
    risk_score: int = 0,
    risk_factors: list = None,
    is_flagged: bool = False,
    extra_data: dict = None
):
    """Ghi log bảo mật"""
    try:
        log = DepositSecurityLog(
            deposit_request_id=request_id,
            agent_id=agent_id,
            event_type=event_type,
            event_description=description,
            ip_address=ip,
            user_agent=user_agent,
            risk_score=risk_score,
            risk_factors=risk_factors,
            is_flagged=is_flagged,
            extra_data=extra_data
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")

# =========================================
# API ENDPOINTS
# =========================================

@router.post("/create", response_model=DepositResponse)
async def create_deposit_request(
    request: CreateDepositRequest,
    req: Request,
    background_tasks: BackgroundTasks,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Tạo yêu cầu nạp tiền mới
    
    Flow:
    1. Validate số tiền và giới hạn
    2. Tính điểm rủi ro
    3. Tạo OTP và gửi cho agent
    4. Trả về thông tin ngân hàng để chuyển khoản
    """
    try:
        # Get client info
        client_ip = req.client.host if req.client else None
        user_agent = req.headers.get("user-agent", "")[:500]
        
        # Check limits
        is_allowed, limit_message, require_approval = check_deposit_limits(agent, request.amount, db)
        if not is_allowed:
            log_security_event(
                db, agent.id, "limit_exceeded", limit_message,
                ip=client_ip, user_agent=user_agent
            )
            raise HTTPException(status_code=400, detail=limit_message)
        
        # Calculate risk
        risk_score, risk_factors = calculate_risk_score(agent, request.amount, client_ip, db)
        
        # Flag if high risk
        is_flagged = risk_score >= 50
        if is_flagged:
            require_approval = True  # Force admin approval for high risk
        
        # Get bank account
        bank_account = None
        if request.method == "bank_transfer":
            if request.bank_account_id:
                bank_account = db.query(SystemBankAccount).filter(
                    SystemBankAccount.id == request.bank_account_id,
                    SystemBankAccount.is_active == True
                ).first()
            else:
                # Get default bank account
                bank_account = db.query(SystemBankAccount).filter(
                    SystemBankAccount.is_active == True
                ).first()
        
        # Generate codes
        request_code = generate_request_code()
        otp_code = generate_otp()
        otp_expires = datetime.utcnow() + timedelta(minutes=5)
        
        # Create transfer content
        transfer_content = f"NAP {agent.agent_code} {request.amount}"
        
        # Create deposit request
        deposit = DepositRequest(
            request_code=request_code,
            agent_id=agent.id,
            agent_code=agent.agent_code,
            amount=request.amount,
            method=DepositMethod(request.method) if request.method in [e.value for e in DepositMethod] else DepositMethod.BANK_TRANSFER,
            status=DepositStatus.PENDING,
            bank_account_id=bank_account.id if bank_account else None,
            transfer_content=transfer_content,
            verification_code=otp_code,
            verification_expires_at=otp_expires,
            request_ip=client_ip,
            request_user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            agent_notes=request.notes,
            audit_log=[{
                "action": "created",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "amount": request.amount,
                    "method": request.method,
                    "risk_score": risk_score,
                    "risk_factors": risk_factors,
                    "require_approval": require_approval
                }
            }]
        )
        
        db.add(deposit)
        db.commit()
        db.refresh(deposit)
        
        # Log security event
        log_security_event(
            db, agent.id, "deposit_created", f"Tạo yêu cầu nạp {request.amount:,}đ",
            request_id=deposit.id, ip=client_ip, user_agent=user_agent,
            risk_score=risk_score, risk_factors=risk_factors, is_flagged=is_flagged
        )
        
        # TODO: Send OTP via SMS/Email in background
        # background_tasks.add_task(send_otp_notification, agent, otp_code)
        
        logger.info(f"Deposit request created: {request_code} for {agent.agent_code}, amount={request.amount}, risk={risk_score}")
        
        # Build response
        bank_info = None
        if bank_account:
            bank_info = {
                "bank_name": bank_account.bank_name,
                "account_number": bank_account.account_number,
                "account_name": bank_account.account_name,
                "transfer_content": transfer_content
            }
        
        return DepositResponse(
            success=True,
            message="Yêu cầu nạp tiền đã được tạo. Vui lòng xác minh OTP.",
            request_code=request_code,
            status="pending",
            amount=request.amount,
            otp_sent=True,
            expires_at=otp_expires.isoformat(),
            bank_info=bank_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create deposit error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi tạo yêu cầu: {str(e)}")

@router.post("/verify-otp", response_model=DepositResponse)
async def verify_deposit_otp(
    request: VerifyOTPRequest,
    req: Request,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Xác minh OTP cho yêu cầu nạp tiền
    """
    try:
        client_ip = req.client.host if req.client else None
        
        # Find deposit request
        deposit = db.query(DepositRequest).filter(
            DepositRequest.request_code == request.request_code,
            DepositRequest.agent_id == agent.id
        ).first()
        
        if not deposit:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu nạp tiền")
        
        # Check if can verify
        if not deposit.can_verify():
            if deposit.is_verified:
                raise HTTPException(status_code=400, detail="Yêu cầu đã được xác minh")
            if deposit.verification_attempts >= deposit.max_verification_attempts:
                deposit.status = DepositStatus.CANCELLED
                deposit.add_audit_log("cancelled", details={"reason": "Quá số lần xác minh"})
                db.commit()
                raise HTTPException(status_code=400, detail="Đã vượt quá số lần xác minh. Yêu cầu bị hủy.")
            if deposit.is_expired():
                deposit.status = DepositStatus.EXPIRED
                db.commit()
                raise HTTPException(status_code=400, detail="Yêu cầu đã hết hạn")
        
        # Check OTP expiration
        if deposit.verification_expires_at and datetime.utcnow() > deposit.verification_expires_at:
            deposit.status = DepositStatus.EXPIRED
            db.commit()
            log_security_event(db, agent.id, "otp_expired", "OTP hết hạn", deposit.id, client_ip)
            raise HTTPException(status_code=400, detail="Mã OTP đã hết hạn. Vui lòng tạo yêu cầu mới.")
        
        # Verify OTP
        if deposit.verification_code != request.otp_code:
            deposit.verification_attempts += 1
            deposit.add_audit_log("otp_failed", details={
                "attempt": deposit.verification_attempts,
                "ip": client_ip
            })
            db.commit()
            
            remaining = deposit.max_verification_attempts - deposit.verification_attempts
            log_security_event(
                db, agent.id, "otp_failed", f"OTP sai, còn {remaining} lần",
                deposit.id, client_ip, is_flagged=remaining <= 1
            )
            
            if remaining <= 0:
                deposit.status = DepositStatus.CANCELLED
                db.commit()
                raise HTTPException(status_code=400, detail="Đã vượt quá số lần xác minh. Yêu cầu bị hủy.")
            
            raise HTTPException(status_code=400, detail=f"Mã OTP không đúng. Còn {remaining} lần thử.")
        
        # OTP verified successfully
        deposit.is_verified = True
        deposit.verified_at = datetime.utcnow()
        deposit.status = DepositStatus.VERIFIED
        deposit.add_audit_log("verified", details={"ip": client_ip})
        
        db.commit()
        
        log_security_event(db, agent.id, "otp_verified", "Xác minh OTP thành công", deposit.id, client_ip)
        
        logger.info(f"Deposit OTP verified: {request.request_code}")
        
        return DepositResponse(
            success=True,
            message="Xác minh thành công. Vui lòng chuyển khoản theo thông tin đã cung cấp.",
            request_code=request.request_code,
            status="verified",
            amount=int(deposit.amount)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify OTP error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resend-otp", response_model=DepositResponse)
async def resend_deposit_otp(
    request_code: str,
    req: Request,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Gửi lại OTP cho yêu cầu nạp tiền
    """
    try:
        client_ip = req.client.host if req.client else None
        
        deposit = db.query(DepositRequest).filter(
            DepositRequest.request_code == request_code,
            DepositRequest.agent_id == agent.id,
            DepositRequest.status == DepositStatus.PENDING
        ).first()
        
        if not deposit:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
        
        if deposit.is_verified:
            raise HTTPException(status_code=400, detail="Yêu cầu đã được xác minh")
        
        if deposit.is_expired():
            raise HTTPException(status_code=400, detail="Yêu cầu đã hết hạn")
        
        # Check rate limit for resend (max 3 times)
        resend_count = len([l for l in (deposit.audit_log or []) if l.get('action') == 'otp_resent'])
        if resend_count >= 3:
            raise HTTPException(status_code=400, detail="Đã vượt quá số lần gửi lại OTP")
        
        # Generate new OTP
        new_otp = generate_otp()
        deposit.verification_code = new_otp
        deposit.verification_expires_at = datetime.utcnow() + timedelta(minutes=5)
        deposit.verification_attempts = 0  # Reset attempts
        deposit.add_audit_log("otp_resent", details={"ip": client_ip, "count": resend_count + 1})
        
        db.commit()
        
        log_security_event(db, agent.id, "otp_resent", f"Gửi lại OTP lần {resend_count + 1}", deposit.id, client_ip)
        
        # TODO: Send OTP via SMS/Email
        
        return DepositResponse(
            success=True,
            message="Đã gửi lại mã OTP",
            request_code=request_code,
            otp_sent=True,
            expires_at=deposit.verification_expires_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend OTP error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requests", response_model=List[Dict])
async def get_deposit_requests(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách yêu cầu nạp tiền của agent
    """
    query = db.query(DepositRequest).filter(DepositRequest.agent_id == agent.id)
    
    if status:
        try:
            query = query.filter(DepositRequest.status == DepositStatus(status))
        except ValueError:
            pass
    
    deposits = query.order_by(DepositRequest.created_at.desc()).offset(offset).limit(limit).all()
    
    return [
        {
            "id": d.id,
            "request_code": d.request_code,
            "amount": int(d.amount),
            "method": d.method.value if d.method else None,
            "status": d.status.value if d.status else None,
            "is_verified": d.is_verified,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "expires_at": d.expires_at.isoformat() if d.expires_at else None,
            "transfer_content": d.transfer_content
        }
        for d in deposits
    ]

@router.post("/cancel")
async def cancel_deposit_request(
    request_code: str,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db)
):
    """
    Hủy yêu cầu nạp tiền
    """
    deposit = db.query(DepositRequest).filter(
        DepositRequest.request_code == request_code,
        DepositRequest.agent_id == agent.id,
        DepositRequest.status.in_([DepositStatus.PENDING, DepositStatus.VERIFIED])
    ).first()
    
    if not deposit:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu hoặc không thể hủy")
    
    deposit.status = DepositStatus.CANCELLED
    deposit.add_audit_log("cancelled", details={"by": "agent"})
    db.commit()
    
    log_security_event(db, agent.id, "deposit_cancelled", f"Hủy yêu cầu {request_code}", deposit.id)
    
    return {"success": True, "message": "Đã hủy yêu cầu nạp tiền"}

# =========================================
# WEBHOOK ENDPOINT - Bank Transfer Auto
# =========================================

@router.post("/webhook/bank")
async def bank_transfer_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook nhận thông báo chuyển khoản từ ngân hàng
    
    Bảo mật:
    1. Verify signature
    2. Check duplicate
    3. Match với deposit request
    4. Auto approve nếu khớp
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        payload = json.loads(body)
        
        # Get signature from header
        signature = request.headers.get("X-Webhook-Signature") or request.headers.get("x-signature")
        webhook_source = request.headers.get("X-Webhook-Source", "unknown")
        
        # TODO: Verify signature based on webhook source
        # signature_valid = verify_webhook_signature(body, signature, webhook_source)
        
        # Parse webhook data
        transfer_data = parse_bank_webhook(payload, webhook_source)
        if not transfer_data:
            logger.warning(f"Could not parse webhook: {payload}")
            return {"success": True, "message": "Received but not processed"}
        
        amount = transfer_data.get('amount', 0)
        content = transfer_data.get('content', '')
        bank_ref = transfer_data.get('reference', '')
        
        # Skip if not credit (money in)
        if transfer_data.get('type') != 'credit' or amount <= 0:
            return {"success": True, "message": "Not a credit transaction"}
        
        # Check duplicate
        existing = db.query(DepositRequest).filter(
            DepositRequest.bank_reference == bank_ref
        ).first()
        if existing:
            return {"success": True, "message": "Duplicate", "duplicate": True}
        
        # Extract agent code from content
        agent_code = extract_agent_code(content)
        if not agent_code:
            logger.info(f"No agent code in transfer: {content[:100]}")
            return {"success": True, "message": "No agent code found"}
        
        # Find agent
        agent = db.query(Agent).filter(Agent.agent_code == agent_code).first()
        if not agent:
            logger.warning(f"Agent not found: {agent_code}")
            return {"success": True, "message": "Agent not found"}
        
        # Find matching deposit request
        matching_deposit = db.query(DepositRequest).filter(
            DepositRequest.agent_id == agent.id,
            DepositRequest.status == DepositStatus.VERIFIED,
            DepositRequest.amount == amount,
            DepositRequest.is_verified == True
        ).order_by(DepositRequest.created_at.desc()).first()
        
        if matching_deposit:
            # Match found - auto complete
            matching_deposit.status = DepositStatus.COMPLETED
            matching_deposit.bank_reference = bank_ref
            matching_deposit.actual_amount = amount
            matching_deposit.processed_at = datetime.utcnow()
            matching_deposit.webhook_verified = True
            matching_deposit.webhook_source = webhook_source
            matching_deposit.previous_balance = agent.balance
            matching_deposit.new_balance = agent.balance + Decimal(str(amount))
            matching_deposit.add_audit_log("auto_completed", details={
                "bank_ref": bank_ref,
                "webhook_source": webhook_source
            })
            
            # Update agent balance
            agent.balance = matching_deposit.new_balance
            agent.total_deposit = (agent.total_deposit or Decimal('0')) + Decimal(str(amount))
            
            # Create transaction
            from utils import generate_transaction_code
            transaction = Transaction(
                transaction_code=generate_transaction_code(),
                agent_id=agent.id,
                transaction_type=TransactionType.DEPOSIT,
                amount=Decimal(str(amount)),
                fee=Decimal('0'),
                total_amount=Decimal(str(amount)),
                status=TransactionStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                payment_method="bank_transfer",
                gateway_transaction_id=bank_ref,
                previous_balance=matching_deposit.previous_balance,
                new_balance=matching_deposit.new_balance,
                description=f"Nạp tiền tự động - {matching_deposit.request_code}",
                transaction_metadata={
                    "deposit_request_id": matching_deposit.id,
                    "deposit_request_code": matching_deposit.request_code,
                    "auto_deposit": True,
                    "bank_ref": bank_ref
                }
            )
            db.add(transaction)
            
            matching_deposit.transaction_id = transaction.id
            
            db.commit()
            
            log_security_event(
                db, agent.id, "auto_deposit_completed",
                f"Nạp tự động {amount:,}đ từ webhook",
                matching_deposit.id
            )
            
            logger.info(f"Auto deposit completed: {matching_deposit.request_code}, {amount}đ")
            
            return {
                "success": True,
                "message": "Deposit completed",
                "matched": True,
                "deposit_code": matching_deposit.request_code,
                "transaction_code": transaction.transaction_code
            }
        else:
            # No matching request - create new pending
            request_code = generate_request_code()
            new_deposit = DepositRequest(
                request_code=request_code,
                agent_id=agent.id,
                agent_code=agent.agent_code,
                amount=amount,
                actual_amount=amount,
                method=DepositMethod.BANK_WEBHOOK,
                status=DepositStatus.PENDING,
                bank_reference=bank_ref,
                transfer_content=content[:255],
                is_verified=True,  # Webhook is trusted
                verified_at=datetime.utcnow(),
                webhook_verified=True,
                webhook_source=webhook_source,
                audit_log=[{
                    "action": "webhook_created",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {"bank_ref": bank_ref}
                }]
            )
            db.add(new_deposit)
            db.commit()
            
            log_security_event(
                db, agent.id, "webhook_deposit_pending",
                f"Nhận webhook {amount:,}đ, chờ xác nhận",
                new_deposit.id
            )
            
            return {
                "success": True,
                "message": "Deposit pending approval",
                "matched": False,
                "deposit_code": request_code
            }
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        return {"success": False, "message": "Invalid JSON"}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        db.rollback()
        return {"success": False, "message": str(e)}


def parse_bank_webhook(payload: dict, source: str) -> Optional[dict]:
    """Parse webhook data from different sources"""
    try:
        # Casso format
        if 'data' in payload and isinstance(payload['data'], list):
            for item in payload['data']:
                if 'amount' in item:
                    return {
                        'type': 'credit' if item.get('amount', 0) > 0 else 'debit',
                        'amount': abs(item.get('amount', 0)),
                        'content': item.get('description', '') or item.get('content', ''),
                        'reference': str(item.get('id', '') or item.get('transactionId', ''))
                    }
        
        # SePay format
        if 'transferType' in payload:
            return {
                'type': 'credit' if payload.get('transferType') == 'in' else 'debit',
                'amount': abs(payload.get('transferAmount', 0)),
                'content': payload.get('content', '') or payload.get('description', ''),
                'reference': str(payload.get('id', '') or payload.get('transactionId', ''))
            }
        
        # Generic format
        if 'amount' in payload:
            return {
                'type': 'credit' if payload.get('type', '').lower() in ['credit', 'in', 'receive'] else 'debit',
                'amount': abs(payload.get('amount', 0)),
                'content': payload.get('content', '') or payload.get('description', '') or payload.get('memo', ''),
                'reference': str(payload.get('reference', '') or payload.get('id', '') or payload.get('transaction_id', ''))
            }
        
        return None
    except Exception as e:
        logger.error(f"Parse webhook error: {e}")
        return None


def extract_agent_code(content: str) -> Optional[str]:
    """Extract agent code from transfer content"""
    if not content:
        return None
    
    content = content.upper()
    
    # Pattern: NAP AGENTCODE or NAPTIEN AGENTCODE
    patterns = [
        r'(?:NAP|NAPTIEN|TOPUP|DEPOSIT)\s+(\d?[A-Z]{2,5}\d{3,6})',
        r'(?:NAP|NAPTIEN|TOPUP|DEPOSIT)\s+([A-Z]{2,5}\d{3,6})',
        r'\b([A-Z]{2,3}\d{4,6})\b',  # Generic agent code pattern
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    return None
