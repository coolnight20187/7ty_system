"""
Email Webhook Router - API để cấu hình và quản lý đọc email ngân hàng
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, EmailStr
import logging
import json
from datetime import datetime
from decimal import Decimal

from database import get_db
from models import Agent, Transaction, TransactionType, TransactionStatus, AgentStatus
from utils import generate_transaction_code
from services.email_reader_service import EmailReaderService, email_reader_manager, BankTransaction

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class EmailConfigRequest(BaseModel):
    email: EmailStr
    password: str
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    bank_account: Optional[str] = None  # Số TK ngân hàng liên kết


class EmailConfigResponse(BaseModel):
    email: str
    imap_server: str
    imap_port: int
    bank_account: Optional[str]
    enabled: bool


class TestEmailRequest(BaseModel):
    email: EmailStr
    password: str
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None


class EmailTransactionResponse(BaseModel):
    bank_code: str
    amount: float
    content: str
    transaction_type: str
    account_number: str
    balance: Optional[float]
    transaction_time: Optional[str]


# Helper functions
def parse_agent_code_from_content(content: str) -> Optional[str]:
    """Parse mã đại lý từ nội dung chuyển khoản"""
    import re
    
    if not content:
        return None
    
    content = content.upper().strip()
    content = re.sub(r'[^A-Z0-9\s]', ' ', content)
    content = ' '.join(content.split())
    
    # Pattern kèm từ khóa
    keyword_patterns = [
        r'(?:NAP|NAPTIEN|TOPUP|DEPOSIT)\s+(\d?[A-Z]{2,5}\d{3,6})',
        r'(?:NAP|NAPTIEN|TOPUP|DEPOSIT)\s+([A-Z]{2,5}\d{3,6})',
        r'(?:7TY|DL|DAILY|AGENT)\s+(\d?[A-Z]{2,5}\d{3,6})',
        r'(\d?[A-Z]{2,5}\d{3,6})\s+(?:NAP|NAPTIEN|TOPUP)',
    ]
    
    specific_patterns = [
        r'\b(\d?[A-Z]{2,5}\d{3,6})\b',
        r'\b([A-Z]{2,5}\d{3,6})\b',
    ]
    
    for pattern in keyword_patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    for pattern in specific_patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    return None


async def process_email_transaction(transaction: BankTransaction, db: Session):
    """Xử lý giao dịch từ email"""
    
    # Chỉ xử lý giao dịch tiền vào
    if transaction.transaction_type != 'credit':
        logger.info(f"Skipping non-credit transaction: {transaction.transaction_type}")
        return None
    
    # Parse mã đại lý
    agent_code = parse_agent_code_from_content(transaction.content)
    
    if not agent_code:
        logger.warning(f"Could not parse agent code from email: {transaction.content[:100]}")
        return {
            'success': False,
            'message': 'Không tìm thấy mã đại lý trong nội dung',
            'matched': False
        }
    
    # Tìm đại lý
    agent = db.query(Agent).filter(
        Agent.agent_code == agent_code.upper(),
        Agent.status == AgentStatus.ACTIVE
    ).first()
    
    if not agent:
        logger.warning(f"Agent not found: {agent_code}")
        return {
            'success': False,
            'message': f'Không tìm thấy đại lý: {agent_code}',
            'matched': False
        }
    
    # Kiểm tra giao dịch trùng lặp
    existing = db.query(Transaction).filter(
        Transaction.gateway_transaction_id == transaction.transaction_id
    ).first()
    
    if existing:
        logger.info(f"Duplicate transaction: {transaction.transaction_id}")
        return {
            'success': True,
            'message': 'Giao dịch đã được xử lý trước đó',
            'duplicate': True
        }
    
    # Tạo giao dịch nạp tiền
    amount = Decimal(str(transaction.amount))
    previous_balance = agent.balance
    
    new_transaction = Transaction(
        transaction_code=generate_transaction_code(),
        agent_id=agent.id,
        user_id=agent.user_id,
        transaction_type=TransactionType.DEPOSIT,
        amount=amount,
        total_amount=amount,
        status=TransactionStatus.COMPLETED,
        payment_method="bank_transfer",
        description=f"Nạp tiền qua email - {transaction.bank_code}",
        gateway_transaction_id=transaction.transaction_id,
        gateway_response={
            'source': 'email_reader',
            'bank_code': transaction.bank_code,
            'account_number': transaction.account_number,
            'content': transaction.content,
            'raw': transaction.raw_content[:500]
        },
        completed_at=datetime.utcnow()
    )
    
    db.add(new_transaction)
    
    # Cập nhật số dư đại lý
    agent.balance += amount
    agent.total_deposit += amount
    
    db.commit()
    
    logger.info(f"Email deposit successful: {agent_code} +{amount} -> Balance: {agent.balance}")
    
    return {
        'success': True,
        'message': 'Nạp tiền thành công',
        'matched': True,
        'data': {
            'transaction_code': new_transaction.transaction_code,
            'agent_code': agent_code,
            'amount': float(amount),
            'previous_balance': float(previous_balance),
            'new_balance': float(agent.balance)
        }
    }


# API Endpoints
@router.post("/email/test-connection")
async def test_email_connection(request: TestEmailRequest):
    """Test kết nối email"""
    reader = EmailReaderService(
        request.email,
        request.password,
        request.imap_server,
        request.imap_port
    )
    
    result = reader.test_connection()
    return result


@router.post("/email/config")
async def add_email_config(
    request: EmailConfigRequest,
    db: Session = Depends(get_db)
):
    """Thêm cấu hình email để đọc giao dịch ngân hàng"""
    
    success = email_reader_manager.add_email_config(
        request.email,
        request.password,
        request.imap_server,
        request.imap_port,
        request.bank_account
    )
    
    if success:
        # Lưu config vào database
        try:
            from models import SystemConfig
            
            existing = db.query(SystemConfig).filter(
                SystemConfig.key == f"email_config_{request.email}"
            ).first()
            
            config_data = {
                'email': request.email,
                'password': request.password,  # Trong production nên encrypt
                'imap_server': request.imap_server or '',
                'imap_port': request.imap_port or 993,
                'bank_account': request.bank_account or '',
                'enabled': True
            }
            
            if existing:
                existing.value = json.dumps(config_data)
            else:
                new_config = SystemConfig(
                    key=f"email_config_{request.email}",
                    value=json.dumps(config_data),
                    description=f"Email config for {request.email}"
                )
                db.add(new_config)
            
            db.commit()
        except Exception as e:
            logger.error(f"Error saving email config to DB: {e}")
        
        return {
            'success': True,
            'message': f'Đã thêm cấu hình email: {request.email}'
        }
    else:
        raise HTTPException(
            status_code=400,
            detail='Không thể kết nối email. Kiểm tra lại thông tin đăng nhập.'
        )


@router.get("/email/configs")
async def get_email_configs():
    """Lấy danh sách cấu hình email"""
    configs = email_reader_manager.get_all_configs()
    return {
        'success': True,
        'configs': configs
    }


@router.delete("/email/config/{email}")
async def remove_email_config(email: str, db: Session = Depends(get_db)):
    """Xóa cấu hình email"""
    email_reader_manager.remove_email_config(email)
    
    # Xóa từ database
    try:
        from models import SystemConfig
        db.query(SystemConfig).filter(
            SystemConfig.key == f"email_config_{email}"
        ).delete()
        db.commit()
    except Exception as e:
        logger.error(f"Error removing email config from DB: {e}")
    
    return {
        'success': True,
        'message': f'Đã xóa cấu hình email: {email}'
    }


@router.post("/email/check-now")
async def check_emails_now(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Kiểm tra email ngay lập tức"""
    
    try:
        transactions = await email_reader_manager.check_all_emails()
        
        results = []
        for tx in transactions:
            result = await process_email_transaction(tx, db)
            if result:
                results.append(result)
        
        return {
            'success': True,
            'message': f'Đã kiểm tra email, tìm thấy {len(transactions)} giao dịch',
            'transactions': len(transactions),
            'processed': len([r for r in results if r.get('success')]),
            'results': results
        }
    except Exception as e:
        logger.error(f"Error checking emails: {e}")
        raise HTTPException(
            status_code=500,
            detail=f'Lỗi kiểm tra email: {str(e)}'
        )


@router.get("/email/transactions")
async def get_email_transactions(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Lấy giao dịch từ email trong X giờ gần đây"""
    
    all_transactions = []
    
    for email, reader in email_reader_manager._readers.items():
        try:
            transactions = reader.fetch_bank_emails(since_hours=hours, mark_as_read=False)
            for tx in transactions:
                all_transactions.append({
                    'email': email,
                    'bank_code': tx.bank_code,
                    'amount': tx.amount,
                    'content': tx.content,
                    'transaction_type': tx.transaction_type,
                    'account_number': tx.account_number,
                    'balance': tx.balance,
                    'transaction_time': tx.transaction_time.isoformat() if tx.transaction_time else None
                })
        except Exception as e:
            logger.error(f"Error fetching from {email}: {e}")
    
    return {
        'success': True,
        'transactions': all_transactions
    }


@router.post("/email/start-auto-check")
async def start_auto_check(interval: int = 60):
    """Bắt đầu tự động kiểm tra email"""
    email_reader_manager._check_interval = interval
    # Note: Background task cần được start từ main.py
    return {
        'success': True,
        'message': f'Đã cấu hình tự động kiểm tra mỗi {interval} giây'
    }


@router.post("/email/stop-auto-check")
async def stop_auto_check():
    """Dừng tự động kiểm tra email"""
    email_reader_manager.stop_background_checker()
    return {
        'success': True,
        'message': 'Đã dừng tự động kiểm tra email'
    }
