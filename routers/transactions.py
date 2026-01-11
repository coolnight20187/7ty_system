from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

from database import get_db
from models import User, Transaction, Agent, Bill, TransactionType, TransactionStatus
from schemas import (
    TransactionResponse, 
    TransactionCreate, 
    TransactionUpdate,
    TransactionFilter,
    TransactionStatsResponse,
    PaginatedResponse,
    PaginationParams,
    ExportRequest,
    SuccessResponse
)
from dependencies import get_current_active_user, get_current_active_admin
from utils import generate_transaction_code

router = APIRouter(tags=["transactions"])

@router.get("/", response_model=PaginatedResponse)
def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    agent_id: Optional[int] = None,
    bill_id: Optional[int] = None,
    transaction_type: Optional[TransactionType] = None,
    status: Optional[TransactionStatus] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    search: Optional[str] = None,
    source: Optional[str] = Query(None, description="Filter by source: 'agent', 'card', 'staff'"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách giao dịch với phân trang và lọc
    """
    try:
        query = db.query(Transaction)
        
        # Lọc theo nguồn giao dịch
        if source == 'agent':
            query = query.filter(Transaction.agent_id.isnot(None))
        elif source == 'card':
            query = query.filter(Transaction.agent_id.is_(None), Transaction.user_id.is_(None))
        elif source == 'staff':
            query = query.filter(Transaction.agent_id.is_(None), Transaction.user_id.isnot(None))
        
        # Lọc theo agent
        if agent_id:
            query = query.filter(Transaction.agent_id == agent_id)
        
        # Lọc theo bill
        if bill_id:
            query = query.filter(Transaction.bill_id == bill_id)
        
        # Lọc theo loại giao dịch
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        # Lọc theo trạng thái
        if status:
            query = query.filter(Transaction.status == status)
        
        # Lọc theo thời gian
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(Transaction.created_at >= start)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ngày bắt đầu không đúng định dạng (YYYY-MM-DD)"
                )
        
        if end_date:
            try:
                end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(Transaction.created_at < end)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ngày kết thúc không đúng định dạng (YYYY-MM-DD)"
                )
        
        # Lọc theo số tiền
        if min_amount:
            query = query.filter(Transaction.amount >= min_amount)
        
        if max_amount:
            query = query.filter(Transaction.amount <= max_amount)
        
        # Tìm kiếm
        if search:
            search_term = f"%{search}%"
            query = query.join(Agent, Transaction.agent_id == Agent.id)
            query = query.filter(
                or_(
                    Transaction.transaction_code.ilike(search_term),
                    Agent.full_name.ilike(search_term),
                    Agent.agent_code.ilike(search_term),
                    Transaction.description.ilike(search_term)
                )
            )
        
        # Tính tổng
        total = query.count()
        
        # Sắp xếp và phân trang
        transactions = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
        
        return PaginatedResponse(
            success=True,
            page=skip // limit + 1,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
            items=transactions
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy danh sách giao dịch: {str(e)}"
        )

@router.get("/stats", response_model=TransactionStatsResponse)
def get_transaction_stats(
    period: str = Query("today", pattern="^(today|yesterday|week|month|year|custom)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Lấy thống kê giao dịch theo khoảng thời gian
    """
    try:
        today = datetime.now().date()
        
        # Xác định khoảng thời gian
        if period == "today":
            date_filter = func.date(Transaction.created_at) == today
        elif period == "yesterday":
            yesterday = today - timedelta(days=1)
            date_filter = func.date(Transaction.created_at) == yesterday
        elif period == "week":
            week_ago = today - timedelta(days=7)
            date_filter = func.date(Transaction.created_at) >= week_ago
        elif period == "month":
            month_ago = today - timedelta(days=30)
            date_filter = func.date(Transaction.created_at) >= month_ago
        elif period == "year":
            year_ago = today - timedelta(days=365)
            date_filter = func.date(Transaction.created_at) >= year_ago
        elif period == "custom" and start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_filter = and_(
                    func.date(Transaction.created_at) >= start,
                    func.date(Transaction.created_at) <= end
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ngày không đúng định dạng (YYYY-MM-DD)"
                )
        else:
            date_filter = func.date(Transaction.created_at) == today
        
        # Thống kê tổng hợp
        stats_query = db.query(
            func.count(Transaction.id).label("total_count"),
            func.sum(Transaction.amount).label("total_amount"),
            func.avg(Transaction.amount).label("avg_amount"),
            func.max(Transaction.amount).label("max_amount"),
            func.min(Transaction.amount).label("min_amount")
        ).filter(date_filter)
        
        stats = stats_query.first()
        
        # Thống kê theo loại giao dịch
        type_stats_query = db.query(
            Transaction.transaction_type,
            func.count(Transaction.id).label("count"),
            func.sum(Transaction.amount).label("amount")
        ).filter(date_filter).group_by(Transaction.transaction_type)
        
        type_stats = type_stats_query.all()
        
        # Thống kê theo trạng thái
        status_stats_query = db.query(
            Transaction.status,
            func.count(Transaction.id).label("count"),
            func.sum(Transaction.amount).label("amount")
        ).filter(date_filter).group_by(Transaction.status)
        
        status_stats = status_stats_query.all()
        
        return TransactionStatsResponse(
            total_count=stats.total_count or 0,
            total_amount=float(stats.total_amount or 0),
            avg_amount=float(stats.avg_amount or 0),
            max_amount=float(stats.max_amount or 0),
            min_amount=float(stats.min_amount or 0),
            by_type=[
                {
                    "type": item.transaction_type,
                    "count": item.count,
                    "amount": float(item.amount or 0)
                }
                for item in type_stats
            ],
            by_status=[
                {
                    "status": item.status,
                    "count": item.count,
                    "amount": float(item.amount or 0)
                }
                for item in status_stats
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy thống kê giao dịch: {str(e)}"
        )

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lấy thông tin chi tiết giao dịch
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giao dịch"
        )
    
    # Kiểm tra quyền truy cập
    if current_user.role != "admin" and transaction.agent_id != current_user.agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập giao dịch này"
        )
    
    return transaction

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Tạo giao dịch mới
    """
    try:
        # Kiểm tra đại lý
        agent = db.query(Agent).filter(Agent.id == transaction_data.agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không tìm thấy đại lý"
            )
        
        # Kiểm tra hóa đơn nếu có
        if transaction_data.bill_id:
            bill = db.query(Bill).filter(Bill.id == transaction_data.bill_id).first()
            if not bill:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không tìm thấy hóa đơn"
                )
        
        # Tạo mã giao dịch
        transaction_code = generate_transaction_code(transaction_data.transaction_type)
        
        # Tạo giao dịch
        db_transaction = Transaction(
            **transaction_data.dict(),
            transaction_code=transaction_code,
            created_by=current_user.id
        )
        
        db.add(db_transaction)
        
        # Cập nhật số dư đại lý nếu giao dịch hoàn thành
        if transaction_data.status == TransactionStatus.COMPLETED:
            if transaction_data.transaction_type in [TransactionType.DEPOSIT, TransactionType.PAYMENT]:
                agent.balance += transaction_data.amount
            elif transaction_data.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.FEE]:
                if agent.balance < transaction_data.amount:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Số dư đại lý không đủ"
                    )
                agent.balance -= transaction_data.amount
        
        db.commit()
        db.refresh(db_transaction)
        
        return db_transaction
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo giao dịch: {str(e)}"
        )

@router.put("/{transaction_id}", response_model=Dict[str, Any])
def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Cập nhật thông tin giao dịch
    """
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy giao dịch"
            )
        
        # Lưu trạng thái và số tiền cũ
        old_status = transaction.status
        old_amount = transaction.amount
        old_type = transaction.transaction_type
        
        # Cập nhật thông tin
        update_data = transaction_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(transaction, field, value)
        
        transaction.updated_at = datetime.now()
        
        # Nếu trạng thái thay đổi thành COMPLETED, cập nhật số dư đại lý
        if (transaction.status == TransactionStatus.COMPLETED and 
            old_status != TransactionStatus.COMPLETED):
            
            agent = db.query(Agent).filter(Agent.id == transaction.agent_id).first()
            if agent:
                if transaction.transaction_type in [TransactionType.DEPOSIT, TransactionType.PAYMENT]:
                    agent.balance += transaction.amount
                elif transaction.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.FEE]:
                    if agent.balance < transaction.amount:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Số dư đại lý không đủ"
                        )
                    agent.balance -= transaction.amount
        
        # Nếu số tiền hoặc loại giao dịch thay đổi
        elif transaction.status == TransactionStatus.COMPLETED:
            agent = db.query(Agent).filter(Agent.id == transaction.agent_id).first()
            if agent:
                # Hoàn tác số tiền cũ
                if old_type in [TransactionType.DEPOSIT, TransactionType.PAYMENT]:
                    agent.balance -= old_amount
                elif old_type in [TransactionType.WITHDRAWAL, TransactionType.FEE]:
                    agent.balance += old_amount
                
                # Áp dụng số tiền mới
                if transaction.transaction_type in [TransactionType.DEPOSIT, TransactionType.PAYMENT]:
                    agent.balance += transaction.amount
                elif transaction.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.FEE]:
                    if agent.balance < transaction.amount:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Số dư đại lý không đủ"
                        )
                    agent.balance -= transaction.amount
        
        db.commit()
        db.refresh(transaction)
        
        return {
            "success": True,
            "message": "Cập nhật giao dịch thành công",
            "data": {
                "id": transaction.id,
                "transaction_code": transaction.transaction_code,
                "status": transaction.status.value if transaction.status else None,
                "amount": str(transaction.amount),
                "notes": transaction.notes
            }
        }
        
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật giao dịch: {str(e)}"
        )

@router.delete("/{transaction_id}", response_model=SuccessResponse)
def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Xóa giao dịch (chỉ dành cho admin)
    """
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giao dịch"
        )
    
    # Không cho xóa giao dịch đã hoàn thành
    if transaction.status == TransactionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa giao dịch đã hoàn thành"
        )
    
    try:
        db.delete(transaction)
        db.commit()
        
        return SuccessResponse(
            success=True,
            message="Xóa giao dịch thành công"
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xóa giao dịch: {str(e)}"
        )

@router.post("/export", response_model=SuccessResponse)
def export_transactions(
    filter_data: TransactionFilter,
    format: str = Query("excel", pattern="^(excel|csv)$"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Xuất danh sách giao dịch ra file Excel hoặc CSV
    """
    try:
        # Áp dụng filter
        query = db.query(Transaction)
        
        if filter_data.agent_id:
            query = query.filter(Transaction.agent_id == filter_data.agent_id)
        
        if filter_data.transaction_type:
            query = query.filter(Transaction.transaction_type == filter_data.transaction_type)
        
        if filter_data.status:
            query = query.filter(Transaction.status == filter_data.status)
        
        if filter_data.start_date:
            try:
                start = datetime.strptime(filter_data.start_date, "%Y-%m-%d")
                query = query.filter(Transaction.created_at >= start)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ngày bắt đầu không đúng định dạng (YYYY-MM-DD)"
                )
        
        if filter_data.end_date:
            try:
                end = datetime.strptime(filter_data.end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(Transaction.created_at < end)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ngày kết thúc không đúng định dạng (YYYY-MM-DD)"
                )
        
        if filter_data.min_amount:
            query = query.filter(Transaction.amount >= filter_data.min_amount)
        
        if filter_data.max_amount:
            query = query.filter(Transaction.amount <= filter_data.max_amount)
        
        transactions = query.order_by(Transaction.created_at.desc()).all()
        
        # Chuẩn bị dữ liệu
        data = []
        for t in transactions:
            data.append({
                "Mã GD": t.transaction_code,
                "Đại lý": t.agent.full_name if t.agent else "",
                "Mã ĐL": t.agent.agent_code if t.agent else "",
                "Loại GD": t.transaction_type,
                "Số tiền": float(t.amount),
                "Phí": float(t.fee),
                "Tổng cộng": float(t.amount + t.fee),
                "Trạng thái": t.status,
                "Mô tả": t.description or "",
                "Ngày tạo": t.created_at.strftime("%d/%m/%Y %H:%M"),
                "Người tạo": t.creator.full_name if t.creator else ""
            })
        
        # Tạo DataFrame
        df = pd.DataFrame(data)
        
        # Tạo tên file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transactions_export_{timestamp}"
        
        # Xuất file
        if format == "excel":
            file_path = f"/tmp/{filename}.xlsx"
            df.to_excel(file_path, index=False)
            file_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_path = f"/tmp/{filename}.csv"
            df.to_csv(file_path, index=False)
            file_type = "text/csv"
        
        # Trong thực tế, bạn nên lưu file vào cloud storage và trả về URL
        # Ở đây chỉ minh họa
        
        return SuccessResponse(
            success=True,
            message=f"Đã xuất {len(transactions)} giao dịch ra file {format}",
            data={
                "file_path": file_path,
                "file_type": file_type,
                "record_count": len(transactions)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xuất dữ liệu: {str(e)}"
        )

@router.post("/{transaction_id}/reverse", response_model=TransactionResponse)
def reverse_transaction(
    transaction_id: int,
    reason: str = Query(..., description="Lý do hoàn tác"),
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Hoàn tác một giao dịch
    """
    try:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy giao dịch"
            )
        
        if transaction.status != TransactionStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể hoàn tác giao dịch đã hoàn thành"
            )
        
        # Tạo giao dịch hoàn tác
        reversal_code = generate_transaction_code(TransactionType.REVERSAL)
        
        reversal_transaction = Transaction(
            transaction_code=reversal_code,
            agent_id=transaction.agent_id,
            bill_id=transaction.bill_id,
            transaction_type=TransactionType.REVERSAL,
            amount=transaction.amount,
            fee=transaction.fee,
            status=TransactionStatus.COMPLETED,
            description=f"Hoàn tác GD {transaction.transaction_code}: {reason}",
            reference_transaction_id=transaction.id,
            created_by=current_user.id
        )
        
        db.add(reversal_transaction)
        
        # Cập nhật số dư đại lý
        agent = db.query(Agent).filter(Agent.id == transaction.agent_id).first()
        if agent:
            # Hoàn tác số tiền: đảo ngược tác động
            if transaction.transaction_type in [TransactionType.DEPOSIT, TransactionType.PAYMENT]:
                agent.balance -= transaction.amount
            elif transaction.transaction_type in [TransactionType.WITHDRAWAL, TransactionType.FEE]:
                agent.balance += transaction.amount
        
        # Đánh dấu giao dịch gốc đã bị hoàn tác
        transaction.status = TransactionStatus.REVERSED
        transaction.updated_at = datetime.now()
        
        db.commit()
        db.refresh(reversal_transaction)
        
        return reversal_transaction
        
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi hoàn tác giao dịch: {str(e)}"
        )