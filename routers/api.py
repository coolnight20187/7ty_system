from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import hashlib
import hmac
import json

from database import get_db
from models import User, Agent, Bill, Transaction, TransactionType, TransactionStatus, BillStatus
from schemas import (
    ApiBillResponse,
    ApiBillPaymentRequest,
    ApiBillPaymentResponse,
    ApiBalanceResponse,
    ApiTransactionResponse,
    ApiTopUpRequest,
    ApiTopUpResponse,
    ApiCheckBillRequest,
    ApiCheckBillResponse,
    ApiWebhookConfig,
    ApiAgentInfoResponse,
    SuccessResponse,
    PaginatedResponse
)
from dependencies import get_api_key
from utils import generate_bill_code, generate_transaction_code, encrypt_data, decrypt_data
from services.webhook_service import send_webhook_notification

router = APIRouter(tags=["api"])

# API Authentication Middleware
async def verify_api_signature(
    x_api_key: str = Header(...),
    x_timestamp: str = Header(...),
    x_signature: str = Header(...),
    body: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """
    Xác thực chữ ký API
    """
    # Lấy thông tin agent từ API key
    agent = db.query(Agent).filter(Agent.api_key == x_api_key).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key không hợp lệ"
        )
    
    if agent.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đại lý chưa được kích hoạt"
        )
    
    # Kiểm tra timestamp (chấp nhận chênh lệch 5 phút)
    try:
        timestamp = datetime.strptime(x_timestamp, "%Y-%m-%dT%H:%M:%S")
        now = datetime.now()
        
        if abs((now - timestamp).total_seconds()) > 300:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Timestamp không hợp lệ"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timestamp không đúng định dạng"
        )
    
    # Tạo chữ ký để so sánh
    message = f"{x_timestamp}{json.dumps(body) if body else ''}"
    expected_signature = hmac.new(
        agent.api_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chữ ký không hợp lệ"
        )
    
    return agent

@router.get("/balance", response_model=ApiBalanceResponse)
async def get_balance(
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Lấy số dư tài khoản đại lý
    """
    return ApiBalanceResponse(
        success=True,
        agent_code=agent.agent_code,
        balance=float(agent.balance),
        credit_limit=float(agent.credit_limit),
        available_balance=float(agent.balance + agent.credit_limit),
        currency="VND",
        last_updated=datetime.now().isoformat()
    )

@router.post("/bills/check", response_model=ApiCheckBillResponse)
async def check_bill(
    request: ApiCheckBillRequest,
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Kiểm tra thông tin hóa đơn
    """
    try:
        # Tìm hóa đơn theo mã khách hàng và kỳ
        bill = db.query(Bill).filter(
            and_(
                Bill.customer_code == request.customer_code,
                Bill.period == request.period,
                Bill.status.in_(["in_stock", "pending"])
            )
        ).first()
        
        if not bill:
            return ApiCheckBillResponse(
                success=False,
                message="Không tìm thấy hóa đơn",
                data=None
            )
        
        return ApiCheckBillResponse(
            success=True,
            message="Tìm thấy hóa đơn",
            data={
                "bill_id": bill.id,
                "bill_code": bill.bill_code,
                "customer_code": bill.customer_code,
                "customer_name": bill.customer_name,
                "customer_address": bill.customer_address,
                "period": bill.period,
                "total_amount": float(bill.total_amount),
                "due_date": bill.due_date.isoformat() if bill.due_date else None,
                "status": bill.status,
                "created_at": bill.created_at.isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi kiểm tra hóa đơn: {str(e)}"
        )

@router.post("/bills/pay", response_model=ApiBillPaymentResponse)
async def pay_bill(
    request: ApiBillPaymentRequest,
    background_tasks: BackgroundTasks,
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Thanh toán hóa đơn
    """
    try:
        # Tìm hóa đơn
        bill = db.query(Bill).filter(
            and_(
                Bill.id == request.bill_id,
                Bill.status.in_(["in_stock", "pending"])
            )
        ).first()
        
        if not bill:
            return ApiBillPaymentResponse(
                success=False,
                message="Không tìm thấy hóa đơn hoặc hóa đơn không hợp lệ",
                transaction_id=None,
                new_balance=float(agent.balance)
            )
        
        # Kiểm tra số dư
        total_amount = float(bill.total_amount)
        if float(agent.balance) < total_amount:
            return ApiBillPaymentResponse(
                success=False,
                message="Số dư không đủ",
                transaction_id=None,
                new_balance=float(agent.balance)
            )
        
        # Tạo mã giao dịch
        transaction_code = generate_transaction_code(TransactionType.PAYMENT)
        
        # Tạo giao dịch thanh toán
        transaction = Transaction(
            transaction_code=transaction_code,
            agent_id=agent.id,
            bill_id=bill.id,
            transaction_type=TransactionType.PAYMENT,
            amount=total_amount,
            fee=request.fee or 0,
            status=TransactionStatus.COMPLETED,
            description=f"Thanh toán hóa đơn {bill.bill_code} qua API",
            metadata=json.dumps({
                "api_reference": request.reference_id,
                "payment_method": request.payment_method,
                "customer_ip": request.customer_ip,
                "device_info": request.device_info
            }),
            created_by=agent.user_id
        )
        
        db.add(transaction)
        
        # Cập nhật số dư đại lý
        agent.balance -= total_amount
        
        # Cập nhật trạng thái hóa đơn
        bill.status = BillStatus.SOLD
        bill.sold_to = agent.id
        bill.sold_at = datetime.now()
        bill.payment_method = request.payment_method or "api"
        
        db.commit()
        db.refresh(transaction)
        
        # Gửi webhook thông báo (bất đồng bộ)
        if agent.webhook_url and agent.webhook_enabled:
            webhook_data = {
                "event": "bill_paid",
                "agent_code": agent.agent_code,
                "bill_code": bill.bill_code,
                "transaction_id": transaction.id,
                "transaction_code": transaction.transaction_code,
                "amount": float(total_amount),
                "timestamp": datetime.now().isoformat(),
                "reference_id": request.reference_id
            }
            
            background_tasks.add_task(
                send_webhook_notification,
                agent.webhook_url,
                webhook_data,
                agent.webhook_secret
            )
        
        return ApiBillPaymentResponse(
            success=True,
            message="Thanh toán thành công",
            transaction_id=transaction.id,
            transaction_code=transaction.transaction_code,
            bill_code=bill.bill_code,
            amount=float(total_amount),
            fee=float(request.fee or 0),
            new_balance=float(agent.balance),
            payment_time=datetime.now().isoformat()
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thanh toán hóa đơn: {str(e)}"
        )

@router.post("/topup", response_model=ApiTopUpResponse)
async def top_up(
    request: ApiTopUpRequest,
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Nạp tiền vào tài khoản đại lý
    """
    try:
        # Tạo mã giao dịch
        transaction_code = generate_transaction_code(TransactionType.DEPOSIT)
        
        # Tạo giao dịch nạp tiền
        transaction = Transaction(
            transaction_code=transaction_code,
            agent_id=agent.id,
            transaction_type=TransactionType.DEPOSIT,
            amount=request.amount,
            fee=0,
            status=TransactionStatus.PENDING,
            description=f"Nạp tiền qua API: {request.payment_method}",
            metadata=json.dumps({
                "api_reference": request.reference_id,
                "payment_method": request.payment_method,
                "bank_account": request.bank_account,
                "transaction_date": request.transaction_date
            }),
            created_by=agent.user_id
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return ApiTopUpResponse(
            success=True,
            message="Yêu cầu nạp tiền đã được tạo",
            transaction_id=transaction.id,
            transaction_code=transaction.transaction_code,
            amount=float(request.amount),
            status="pending",
            created_at=transaction.created_at.isoformat()
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo yêu cầu nạp tiền: {str(e)}"
        )

@router.get("/transactions", response_model=List[ApiTransactionResponse])
async def get_agent_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    transaction_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Lấy lịch sử giao dịch của đại lý
    """
    try:
        query = db.query(Transaction).filter(Transaction.agent_id == agent.id)
        
        # Lọc theo thời gian
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.created_at >= start)
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.created_at < end)
        
        # Lọc theo loại giao dịch
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        # Lọc theo trạng thái
        if status:
            query = query.filter(Transaction.status == status)
        
        # Phân trang
        transactions = query.order_by(
            Transaction.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        result = []
        for t in transactions:
            result.append(ApiTransactionResponse(
                id=t.id,
                transaction_code=t.transaction_code,
                type=t.transaction_type,
                amount=float(t.amount),
                fee=float(t.fee),
                total=float(t.amount + t.fee),
                status=t.status,
                description=t.description,
                bill_code=t.bill.bill_code if t.bill else None,
                customer_code=t.bill.customer_code if t.bill else None,
                created_at=t.created_at.isoformat(),
                completed_at=t.completed_at.isoformat() if t.completed_at else None
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy lịch sử giao dịch: {str(e)}"
        )

@router.get("/bills/history", response_model=List[ApiBillResponse])
async def get_bill_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    customer_code: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Lấy lịch sử hóa đơn đã thanh toán
    """
    try:
        query = db.query(Bill).filter(
            and_(
                Bill.sold_to == agent.id,
                Bill.status.in_(["sold", "paid"])
            )
        )
        
        # Lọc theo thời gian
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Bill.sold_at >= start)
        
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Bill.sold_at < end)
        
        # Lọc theo trạng thái
        if status:
            query = query.filter(Bill.status == status)
        
        # Lọc theo mã khách hàng
        if customer_code:
            query = query.filter(Bill.customer_code.ilike(f"%{customer_code}%"))
        
        # Phân trang
        bills = query.order_by(
            Bill.sold_at.desc()
        ).offset(offset).limit(limit).all()
        
        result = []
        for b in bills:
            result.append(ApiBillResponse(
                id=b.id,
                bill_code=b.bill_code,
                customer_code=b.customer_code,
                customer_name=b.customer_name,
                customer_address=b.customer_address,
                period=b.period,
                total_amount=float(b.total_amount),
                status=b.status,
                sold_at=b.sold_at.isoformat() if b.sold_at else None,
                paid_at=b.paid_at.isoformat() if b.paid_at else None,
                payment_method=b.payment_method
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy lịch sử hóa đơn: {str(e)}"
        )

@router.get("/agent/info", response_model=ApiAgentInfoResponse)
async def get_agent_info(
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Lấy thông tin đại lý
    """
    # Thống kê hôm nay
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_stats = db.query(
        func.count(Bill.id).label("bill_count"),
        func.sum(Bill.total_amount).label("total_amount")
    ).filter(
        and_(
            Bill.sold_to == agent.id,
            Bill.sold_at >= today_start,
            Bill.status.in_(["sold", "paid"])
        )
    ).first()
    
    # Thống kê tháng này
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    month_stats = db.query(
        func.count(Bill.id).label("bill_count"),
        func.sum(Bill.total_amount).label("total_amount")
    ).filter(
        and_(
            Bill.sold_to == agent.id,
            Bill.sold_at >= month_start,
            Bill.status.in_(["sold", "paid"])
        )
    ).first()
    
    return ApiAgentInfoResponse(
        success=True,
        agent_code=agent.agent_code,
        full_name=agent.full_name,
        company_name=agent.company_name,
        phone=agent.phone,
        email=agent.email,
        balance=float(agent.balance),
        credit_limit=float(agent.credit_limit),
        status=agent.status,
        commission_rate=float(agent.commission_rate),
        today_stats={
            "bill_count": today_stats.bill_count or 0,
            "total_amount": float(today_stats.total_amount or 0)
        },
        month_stats={
            "bill_count": month_stats.bill_count or 0,
            "total_amount": float(month_stats.total_amount or 0)
        },
        api_config={
            "webhook_url": agent.webhook_url,
            "webhook_enabled": agent.webhook_enabled
        }
    )

@router.post("/webhook/config", response_model=SuccessResponse)
async def update_webhook_config(
    config: ApiWebhookConfig,
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Cập nhật cấu hình webhook
    """
    try:
        agent.webhook_url = config.webhook_url
        agent.webhook_secret = config.webhook_secret
        agent.webhook_enabled = config.enabled
        
        db.commit()
        
        return SuccessResponse(
            success=True,
            message="Cập nhật webhook thành công"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật webhook: {str(e)}"
        )

@router.post("/test/webhook", response_model=SuccessResponse)
async def test_webhook(
    background_tasks: BackgroundTasks,
    agent: Agent = Depends(verify_api_signature),
    db: Session = Depends(get_db)
):
    """
    Gửi webhook test để kiểm tra cấu hình
    """
    if not agent.webhook_url or not agent.webhook_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook chưa được cấu hình"
        )
    
    try:
        test_data = {
            "event": "test",
            "agent_code": agent.agent_code,
            "message": "Đây là webhook test từ hệ thống 7TY.VN",
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        
        background_tasks.add_task(
            send_webhook_notification,
            agent.webhook_url,
            test_data,
            agent.webhook_secret
        )
        
        return SuccessResponse(
            success=True,
            message="Đã gửi webhook test"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi gửi webhook test: {str(e)}"
        )

@router.get("/version")
async def get_api_version():
    """
    Lấy thông tin phiên bản API
    """
    return {
        "api_version": "1.0.0",
        "system_version": "4.0.0",
        "supported_features": [
            "balance_check",
            "bill_payment",
            "bill_check",
            "topup",
            "transaction_history",
            "webhook"
        ],
        "rate_limit": {
            "per_minute": 60,
            "per_hour": 1000,
            "per_day": 10000
        },
        "documentation": "https://docs.7ty.vn/api"
    }

@router.post("/encrypt", response_model=SuccessResponse)
async def encrypt_data_api(
    data: Dict[str, Any],
    agent: Agent = Depends(verify_api_signature)
):
    """
    Mã hóa dữ liệu (dùng cho truyền dữ liệu nhạy cảm)
    """
    try:
        encrypted = encrypt_data(json.dumps(data), agent.api_secret)
        
        return SuccessResponse(
            success=True,
            message="Mã hóa thành công",
            data={
                "encrypted_data": encrypted,
                "algorithm": "AES-256-GCM"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi mã hóa dữ liệu: {str(e)}"
        )

@router.post("/decrypt", response_model=SuccessResponse)
async def decrypt_data_api(
    encrypted_data: str,
    agent: Agent = Depends(verify_api_signature)
):
    """
    Giải mã dữ liệu
    """
    try:
        decrypted = decrypt_data(encrypted_data, agent.api_secret)
        
        return SuccessResponse(
            success=True,
            message="Giải mã thành công",
            data={
                "decrypted_data": json.loads(decrypted)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi giải mã dữ liệu: {str(e)}"
        )

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Kiểm tra tình trạng API
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "7TY.VN API",
        "version": "1.0.0"
    }


# ===== BANK WEBHOOK - Nhận thông báo biến động số dư từ ngân hàng =====
import re
import logging

logger = logging.getLogger(__name__)

class BankWebhookPayload:
    """Schema cho webhook từ ngân hàng"""
    pass

@router.post("/bank-webhook", response_model=Dict[str, Any])
async def receive_bank_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Nhận webhook từ ngân hàng khi có giao dịch mới
    
    Hỗ trợ các format phổ biến:
    - Casso (casso.vn)
    - SePay
    - Payos
    - Custom webhook
    
    Cú pháp nội dung chuyển khoản để nạp tiền:
    - NAP [MÃ ĐẠI LÝ] hoặc
    - 7TY [MÃ ĐẠI LÝ] hoặc
    - [MÃ ĐẠI LÝ] NAP
    
    Ví dụ: "NAP 7TY001" hoặc "7TY 7TY001" hoặc "7TY001 NAP"
    """
    try:
        logger.info(f"Received bank webhook: {json.dumps(payload, ensure_ascii=False)[:500]}")
        
        # Parse dữ liệu từ các format khác nhau
        transaction_data = parse_bank_webhook(payload)
        
        if not transaction_data:
            return {
                "success": False,
                "message": "Không thể parse dữ liệu webhook",
                "received": True
            }
        
        # Chỉ xử lý giao dịch tiền vào (credit)
        if transaction_data.get('type') != 'credit':
            logger.info(f"Skipping non-credit transaction: {transaction_data.get('type')}")
            return {
                "success": True,
                "message": "Bỏ qua giao dịch tiền ra",
                "received": True
            }
        
        amount = transaction_data.get('amount', 0)
        content = transaction_data.get('content', '')
        bank_ref = transaction_data.get('reference', '')
        
        if amount <= 0:
            return {
                "success": False,
                "message": "Số tiền không hợp lệ",
                "received": True
            }
        
        # Parse mã đại lý từ nội dung chuyển khoản
        agent_code = parse_agent_code_from_content(content)
        
        if not agent_code:
            logger.warning(f"Could not parse agent code from: {content}")
            # Lưu lại giao dịch chưa xác định để admin review
            background_tasks.add_task(
                save_unmatched_transaction,
                db, amount, content, bank_ref, payload
            )
            return {
                "success": True,
                "message": "Giao dịch đã nhận nhưng không tìm thấy mã đại lý",
                "received": True,
                "matched": False
            }
        
        # Tìm đại lý
        from models import AgentStatus
        agent = db.query(Agent).filter(
            Agent.agent_code == agent_code.upper(),
            Agent.status == AgentStatus.ACTIVE
        ).first()
        
        if not agent:
            logger.warning(f"Agent not found: {agent_code}")
            background_tasks.add_task(
                save_unmatched_transaction,
                db, amount, content, bank_ref, payload
            )
            return {
                "success": True,
                "message": f"Không tìm thấy đại lý: {agent_code}",
                "received": True,
                "matched": False
            }
        
        # Kiểm tra giao dịch trùng lặp (theo bank_ref)
        if bank_ref:
            existing = db.query(Transaction).filter(
                Transaction.gateway_transaction_id == bank_ref
            ).first()
            if existing:
                logger.info(f"Duplicate transaction: {bank_ref}")
                return {
                    "success": True,
                    "message": "Giao dịch đã được xử lý trước đó",
                    "received": True,
                    "duplicate": True,
                    "transaction_code": existing.transaction_code
                }
        
        # Tạo giao dịch nạp tiền tự động
        from decimal import Decimal
        
        previous_balance = agent.balance
        new_balance = previous_balance + Decimal(str(amount))
        
        transaction = Transaction(
            transaction_code=generate_transaction_code(),
            agent_id=agent.id,
            user_id=None,  # Tự động, không có user
            transaction_type=TransactionType.DEPOSIT,
            amount=Decimal(str(amount)),
            fee=Decimal('0'),
            total_amount=Decimal(str(amount)),
            status=TransactionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            payment_method="bank_transfer",
            previous_balance=previous_balance,
            new_balance=new_balance,
            description=f"Nạp tự động từ chuyển khoản: {content[:100]}",
            gateway_transaction_id=bank_ref,
            gateway_response=payload,
            transaction_metadata={
                "auto_deposit": True,
                "bank_content": content,
                "bank_ref": bank_ref,
                "source": "bank_webhook"
            }
        )
        
        # Cập nhật số dư đại lý
        agent.balance = new_balance
        agent.total_deposit = (agent.total_deposit or Decimal('0')) + Decimal(str(amount))
        agent.updated_at = datetime.utcnow()
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"Auto deposit successful: {agent.agent_code} +{amount} -> Balance: {new_balance}")
        
        # Gửi thông báo realtime (nếu có websocket)
        try:
            from routers.websocket import ws_manager
            await ws_manager.broadcast({
                "type": "auto_deposit",
                "data": {
                    "agent_id": agent.id,
                    "agent_code": agent.agent_code,
                    "amount": str(amount),
                    "new_balance": str(new_balance),
                    "transaction_code": transaction.transaction_code,
                    "content": content[:50]
                },
                "message": f"✅ Nạp tự động {amount:,.0f}đ cho {agent.agent_code}"
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send websocket notification: {ws_error}")
        
        return {
            "success": True,
            "message": "Nạp tiền thành công",
            "received": True,
            "matched": True,
            "data": {
                "transaction_code": transaction.transaction_code,
                "agent_code": agent.agent_code,
                "amount": amount,
                "previous_balance": float(previous_balance),
                "new_balance": float(new_balance)
            }
        }
        
    except Exception as e:
        logger.error(f"Bank webhook error: {str(e)}", exc_info=True)
        db.rollback()
        return {
            "success": False,
            "message": f"Lỗi xử lý: {str(e)}",
            "received": True
        }


def parse_bank_webhook(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse dữ liệu webhook từ các nguồn khác nhau
    
    Returns:
        Dict với keys: type, amount, content, reference
    """
    try:
        # Format Casso (casso.vn)
        if 'data' in payload and isinstance(payload['data'], list):
            for item in payload['data']:
                if 'amount' in item:
                    return {
                        'type': 'credit' if item.get('amount', 0) > 0 else 'debit',
                        'amount': abs(item.get('amount', 0)),
                        'content': item.get('description', '') or item.get('content', ''),
                        'reference': item.get('id', '') or item.get('transactionId', '')
                    }
        
        # Format SePay
        if 'transferType' in payload:
            return {
                'type': 'credit' if payload.get('transferType') == 'in' else 'debit',
                'amount': abs(payload.get('transferAmount', 0)),
                'content': payload.get('content', ''),
                'reference': payload.get('id', '') or payload.get('referenceCode', '')
            }
        
        # Format Payos
        if 'code' in payload and 'data' in payload:
            data = payload.get('data', {})
            return {
                'type': 'credit',
                'amount': data.get('amount', 0),
                'content': data.get('description', ''),
                'reference': data.get('orderCode', '') or data.get('paymentLinkId', '')
            }
        
        # Format chung (custom webhook)
        if 'amount' in payload:
            trans_type = payload.get('type', 'credit')
            if trans_type in ['in', 'credit', 'deposit', 'receive', '+']:
                trans_type = 'credit'
            else:
                trans_type = 'debit'
                
            return {
                'type': trans_type,
                'amount': abs(payload.get('amount', 0)),
                'content': payload.get('content', '') or payload.get('description', '') or payload.get('memo', ''),
                'reference': payload.get('reference', '') or payload.get('ref', '') or payload.get('id', '')
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing webhook: {e}")
        return None


def parse_agent_code_from_content(content: str) -> Optional[str]:
    """
    Parse mã đại lý từ nội dung chuyển khoản
    
    Hỗ trợ các cú pháp:
    - NAP 7TY001
    - 7TY 7TY001
    - 7TY001 NAP
    - NAPTIEN 7TY001
    - DL 7TY001 (đại lý)
    - Hoặc chỉ mã đại lý: 7TY001, AG000001
    """
    if not content:
        return None
    
    # Chuẩn hóa content
    content = content.upper().strip()
    # Loại bỏ ký tự đặc biệt nhưng giữ space
    content = re.sub(r'[^A-Z0-9\s]', ' ', content)
    content = ' '.join(content.split())  # Gộp nhiều space thành 1
    
    # Pattern cho mã đại lý - hỗ trợ nhiều format:
    # - 7TY001 (số + chữ + số)
    # - AG000001 (chữ + số)
    # - DL001 (chữ + số)
    agent_code_pattern = r'\b([A-Z0-9]{2,8})\b'  # Tổng quát hơn
    
    # Pattern cụ thể cho các format phổ biến
    specific_patterns = [
        r'\b(\d?[A-Z]{2,5}\d{3,6})\b',  # 7TY001, DL001, AG000001
        r'\b([A-Z]{2,5}\d{3,6})\b',      # DL001, AG000001
    ]
    
    # Pattern kèm từ khóa
    keyword_patterns = [
        r'(?:NAP|NAPTIEN|TOPUP|DEPOSIT)\s+(\d?[A-Z]{2,5}\d{3,6})',  # NAP 7TY001
        r'(?:NAP|NAPTIEN|TOPUP|DEPOSIT)\s+([A-Z]{2,5}\d{3,6})',     # NAP DL001
        r'(?:7TY|DL|DAILY|AGENT)\s+(\d?[A-Z]{2,5}\d{3,6})',         # 7TY 7TY001
        r'(\d?[A-Z]{2,5}\d{3,6})\s+(?:NAP|NAPTIEN|TOPUP)',          # 7TY001 NAP
    ]
    
    # Thử với keyword patterns trước
    for pattern in keyword_patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    # Sau đó thử specific patterns
    for pattern in specific_patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    return None
    
    return None


async def save_unmatched_transaction(db: Session, amount: float, content: str, bank_ref: str, payload: Dict):
    """
    Lưu giao dịch chưa khớp để admin review sau
    """
    try:
        from decimal import Decimal
        
        transaction = Transaction(
            transaction_code=generate_transaction_code(),
            agent_id=None,  # Chưa xác định
            user_id=None,
            transaction_type=TransactionType.DEPOSIT,
            amount=Decimal(str(amount)),
            total_amount=Decimal(str(amount)),
            status=TransactionStatus.PENDING,  # Chờ review
            payment_method="bank_transfer",
            description=f"Chờ xác nhận - Nội dung: {content[:200]}",
            gateway_transaction_id=bank_ref,
            gateway_response=payload,
            transaction_metadata={
                "unmatched": True,
                "bank_content": content,
                "bank_ref": bank_ref,
                "source": "bank_webhook",
                "needs_review": True
            }
        )
        
        db.add(transaction)
        db.commit()
        
        logger.info(f"Saved unmatched transaction: {transaction.transaction_code} - {amount}")
        
    except Exception as e:
        logger.error(f"Error saving unmatched transaction: {e}")
        db.rollback()


@router.get("/unmatched-deposits", response_model=Dict[str, Any])
async def get_unmatched_deposits(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách giao dịch chưa khớp (cần review)
    """
    try:
        from sqlalchemy import desc
        
        query = db.query(Transaction).filter(
            Transaction.agent_id.is_(None),
            Transaction.transaction_type == TransactionType.DEPOSIT,
            Transaction.status == TransactionStatus.PENDING
        ).order_by(desc(Transaction.created_at))
        
        total = query.count()
        deposits = query.offset(skip).limit(limit).all()
        
        result = []
        for d in deposits:
            metadata = d.transaction_metadata or {}
            result.append({
                "id": d.id,
                "transaction_code": d.transaction_code,
                "amount": str(d.amount),
                "content": metadata.get('bank_content', d.description),
                "bank_ref": metadata.get('bank_ref', d.gateway_transaction_id),
                "created_at": d.created_at.isoformat(),
                "status": d.status.value
            })
        
        return {
            "success": True,
            "total": total,
            "items": result
        }
        
    except Exception as e:
        logger.error(f"Error getting unmatched deposits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/match-deposit/{transaction_id}", response_model=Dict[str, Any])
async def match_deposit_to_agent(
    transaction_id: int,
    agent_code: str = Query(..., description="Mã đại lý để khớp"),
    db: Session = Depends(get_db)
):
    """
    Khớp giao dịch chưa xác định với đại lý (thủ công bởi admin)
    """
    try:
        from decimal import Decimal
        
        # Lấy giao dịch
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.agent_id.is_(None),
            Transaction.status == TransactionStatus.PENDING
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy giao dịch hoặc đã được xử lý"
            )
        
        # Tìm đại lý
        agent = db.query(Agent).filter(
            Agent.agent_code == agent_code.upper(),
            Agent.status == "active"
        ).first()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy đại lý: {agent_code}"
            )
        
        # Cập nhật giao dịch
        previous_balance = agent.balance
        new_balance = previous_balance + transaction.amount
        
        transaction.agent_id = agent.id
        transaction.status = TransactionStatus.COMPLETED
        transaction.completed_at = datetime.utcnow()
        transaction.previous_balance = previous_balance
        transaction.new_balance = new_balance
        transaction.notes = f"Matched manually at {datetime.utcnow().isoformat()}"
        
        # Cập nhật số dư đại lý
        agent.balance = new_balance
        agent.total_deposit = (agent.total_deposit or Decimal('0')) + transaction.amount
        agent.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Manually matched deposit {transaction.transaction_code} to {agent.agent_code}")
        
        return {
            "success": True,
            "message": f"Đã nạp {transaction.amount:,.0f}đ cho {agent.agent_code}",
            "data": {
                "transaction_code": transaction.transaction_code,
                "agent_code": agent.agent_code,
                "amount": str(transaction.amount),
                "new_balance": str(new_balance)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error matching deposit: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )