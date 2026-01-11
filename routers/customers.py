# routers/customers.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, or_
from typing import List, Optional
from datetime import datetime, date
import json

from database import get_db
from models import Customer, Bill, User, Agent, UserRole
from schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    CustomerStats, CustomerSearchResponse
)
from dependencies import get_current_user
from utils import validate_vietnamese_phone, validate_email

router = APIRouter(tags=["Khách hàng"])
security = HTTPBearer()

# Helper function to normalize role for comparison (supports both uppercase and lowercase)
def get_role(user):
    """Get normalized role string (lowercase) from user"""
    role = str(user.role).lower() if user.role else ""
    # Handle enum values like "UserRole.ADMIN" -> "admin"
    if "." in role:
        role = role.split(".")[-1]
    return role

def is_admin(user):
    return get_role(user) == "admin"

def is_staff(user):
    return get_role(user) == "staff"

def is_agent(user):
    return get_role(user) == "agent"

def is_admin_or_staff(user):
    return get_role(user) in ["admin", "staff"]

# Danh sách khách hàng
@router.get("/", response_model=List[CustomerResponse])
async def get_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, regex="^(active|inactive)$"),
    province: Optional[str] = None,
    district: Optional[str] = None,
    ward: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    has_bills: Optional[bool] = None,
    min_bills: Optional[int] = Query(None, ge=0),
    max_bills: Optional[int] = Query(None, ge=0),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách khách hàng với bộ lọc"""
    query = db.query(Customer)
    
    # Áp dụng bộ lọc
    if status:
        query = query.filter(Customer.status == status)
    if province:
        query = query.filter(Customer.province.ilike(f"%{province}%"))
    if district:
        query = query.filter(Customer.district.ilike(f"%{district}%"))
    if ward:
        query = query.filter(Customer.ward.ilike(f"%{ward}%"))
    if from_date:
        query = query.filter(Customer.created_at >= from_date)
    if to_date:
        query = query.filter(Customer.created_at <= to_date)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Customer.customer_code.ilike(search_term),
                Customer.customer_name.ilike(search_term),
                Customer.phone.ilike(search_term),
                Customer.email.ilike(search_term),
                Customer.address.ilike(search_term)
            )
        )
    
    # Phân quyền: Đại lý chỉ xem được khách hàng có hóa đơn của mình
    if current_user.role == "agent":
        # Lấy danh sách hóa đơn của đại lý
        agent_bills = db.query(Bill.customer_id).filter(
            Bill.agent_id == current_user.agent_id
        ).distinct().all()
        
        customer_ids = [bill[0] for bill in agent_bills]
        if customer_ids:
            query = query.filter(Customer.id.in_(customer_ids))
        else:
            # Nếu không có hóa đơn nào, trả về danh sách rỗng
            query = query.filter(Customer.id == 0)
    
    # Bộ lọc theo số hóa đơn
    if has_bills is not None or min_bills is not None or max_bills is not None:
        # Thêm subquery để đếm số hóa đơn
        from sqlalchemy import select, func as sql_func
        bill_count = select([
            Bill.customer_id,
            sql_func.count(Bill.id).label('bill_count')
        ]).group_by(Bill.customer_id).alias('bill_count')
        
        query = query.join(
            bill_count,
            Customer.id == bill_count.c.customer_id,
            isouter=True
        )
        
        if has_bills is True:
            query = query.filter(bill_count.c.bill_count > 0)
        elif has_bills is False:
            query = query.filter(
                (bill_count.c.bill_count == 0) | (bill_count.c.bill_count.is_(None))
            )
        
        if min_bills is not None:
            query = query.filter(bill_count.c.bill_count >= min_bills)
        if max_bills is not None:
            query = query.filter(bill_count.c.bill_count <= max_bills)
    
    # Sắp xếp theo ngày tạo mới nhất
    customers = query.order_by(desc(Customer.created_at)).offset(skip).limit(limit).all()
    return customers

# Tạo khách hàng mới
@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Tạo khách hàng mới"""
    # Kiểm tra mã khách hàng đã tồn tại
    existing = db.query(Customer).filter(
        Customer.customer_code == customer_data.customer_code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã khách hàng đã tồn tại"
        )
    
    # Kiểm tra số điện thoại
    if customer_data.phone and not validate_vietnamese_phone(customer_data.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại không hợp lệ"
        )
    
    # Kiểm tra email
    if customer_data.email and not validate_email(customer_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email không hợp lệ"
        )
    
    # Tạo khách hàng - map schema fields to model fields
    customer_dict = customer_data.dict(exclude_unset=True)
    
    # Map customer_name to full_name for the model
    if 'customer_name' in customer_dict:
        customer_dict['full_name'] = customer_dict.pop('customer_name')
    
    # Remove fields not in model
    customer_dict.pop('customer_type', None)
    customer_dict.pop('id_number', None)
    customer_dict.pop('status', None)
    customer_dict.pop('password', None)  # Password field not in model
    
    # Ensure address has a value (model requires it)
    if not customer_dict.get('address'):
        customer_dict['address'] = ''
    
    customer = Customer(**customer_dict)
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return customer

# Liên kết tài khoản user với khách hàng THẺ mới
@router.post("/link", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def link_user_to_customer(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Liên kết tài khoản user hiện có với khách hàng THẺ mới"""
    
    # Kiểm tra quyền
    if not is_admin_or_staff(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền thực hiện thao tác này"
        )
    
    user_id = data.get('user_id')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu user_id"
        )
    
    # Kiểm tra user tồn tại
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản"
        )
    
    # Kiểm tra user đã được liên kết với khách hàng THẺ chưa
    existing_customer = db.query(Customer).filter(Customer.user_id == user_id).first()
    if existing_customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản này đã được liên kết với khách hàng THẺ khác"
        )
    
    # Tạo mã khách hàng nếu chưa có
    customer_code = data.get('customer_code')
    if not customer_code:
        # Auto generate customer code
        import random
        customer_code = f"THE{random.randint(100000, 999999)}"
        
        # Đảm bảo mã không trùng
        while db.query(Customer).filter(Customer.customer_code == customer_code).first():
            customer_code = f"THE{random.randint(100000, 999999)}"
    else:
        # Kiểm tra mã đã tồn tại
        existing = db.query(Customer).filter(Customer.customer_code == customer_code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã khách hàng THẺ đã tồn tại"
            )
    
    # Tạo expiry từ month/year
    expiry_month = data.get('expiry_month', '')
    expiry_year = data.get('expiry_year', '')
    card_expiry = f"{expiry_month}/{expiry_year}" if expiry_month and expiry_year else None
    
    # Tạo khách hàng THẺ mới liên kết với user (thẻ tín dụng)
    customer = Customer(
        customer_code=customer_code,
        user_id=user_id,
        full_name=user.full_name or user.username,
        phone=user.phone,
        email=user.email,
        address=user.address or '',
        city=user.city,
        district=user.district,
        ward=user.ward,
        customer_type=data.get('customer_type', 'individual'),
        bank_name=data.get('bank_name'),
        card_type=data.get('card_type'),
        card_last_digits=data.get('card_last_digits'),
        card_cvv=data.get('card_cvv'),
        card_expiry=card_expiry,
        card_holder_name=data.get('card_holder_name'),
        card_tier=data.get('card_tier'),
        billing_cycle=int(data.get('billing_cycle')) if data.get('billing_cycle') else None,
        credit_limit=data.get('credit_limit'),
        notes=data.get('notes'),
        is_active=True
    )
    
    db.add(customer)
    
    # Cập nhật role của user thành CUSTOMER (uppercase to match PostgreSQL enum)
    user.role = 'CUSTOMER'
    
    db.commit()
    db.refresh(customer)
    
    return customer

# Liên kết user hiện có với customer (từ modal phân quyền)
@router.post("/link-user", status_code=status.HTTP_201_CREATED)
async def link_user_to_customer_quick(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Liên kết nhanh user với customer record (từ modal phân quyền)"""
    
    if not is_admin_or_staff(current_user):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    user_id = data.get('user_id')
    if not user_id:
        raise HTTPException(status_code=400, detail="Thiếu user_id")
    
    # Kiểm tra user tồn tại
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    
    # Kiểm tra đã có customer chưa
    existing = db.query(Customer).filter(Customer.user_id == user_id).first()
    if existing:
        return {"message": "User đã được liên kết với THẺ", "customer_id": existing.id}
    
    # Tạo customer record mới
    customer_code = f"CUS{user_id:06d}"
    customer = Customer(
        customer_code=customer_code,
        full_name=user.full_name or user.username,
        user_id=user_id,
        phone=user.phone,
        email=user.email,
        address=user.address or '',
        city=user.city,
        district=user.district,
        ward=user.ward,
        is_active=True
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return {"message": "Đã liên kết user với Khách THẺ", "customer_id": customer.id}

# Hủy liên kết user với customer
@router.delete("/unlink-user/{user_id}")
async def unlink_user_from_customer(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Hủy liên kết user với customer record"""
    
    if not is_admin_or_staff(current_user):
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    customer = db.query(Customer).filter(Customer.user_id == user_id).first()
    if not customer:
        return {"message": "User không có liên kết với THẺ nào"}
    
    # Xóa liên kết (không xóa customer record, chỉ xóa user_id)
    customer.user_id = None
    db.commit()
    
    return {"message": "Đã hủy liên kết user với Khách THẺ"}

# Lấy chi tiết khách hàng
@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy thông tin chi tiết khách hàng"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng"
        )
    
    # Kiểm tra quyền: Đại lý chỉ xem được khách hàng có hóa đơn của mình
    if current_user.role == "agent":
        has_access = db.query(Bill).filter(
            Bill.customer_id == customer_id,
            Bill.agent_id == current_user.agent_id
        ).first()
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập thông tin khách hàng này"
            )
    
    return customer

# Cập nhật thông tin khách hàng
@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cập nhật thông tin khách hàng"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng"
        )
    
    # Kiểm tra quyền: chỉ admin, staff hoặc người tạo
    if current_user.role not in ["admin", "staff"] and customer.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền chỉnh sửa thông tin khách hàng này"
        )
    
    # Kiểm tra số điện thoại
    if customer_data.phone and not validate_vietnamese_phone(customer_data.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại không hợp lệ"
        )
    
    # Kiểm tra email
    if customer_data.email and not validate_email(customer_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email không hợp lệ"
        )
    
    # Cập nhật thông tin
    update_data = customer_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    customer.updated_at = datetime.now()
    customer.updated_by = current_user.id
    
    db.commit()
    db.refresh(customer)
    
    return customer

# Xóa khách hàng
@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xóa khách hàng"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng"
        )
    
    # Kiểm tra quyền: chỉ admin
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới có quyền xóa khách hàng"
        )
    
    # Kiểm tra xem khách hàng có hóa đơn không
    bill_count = db.query(Bill).filter(Bill.customer_id == customer_id).count()
    if bill_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể xóa khách hàng đang có {bill_count} hóa đơn"
        )
    
    db.delete(customer)
    db.commit()
    
    return {"message": "Xóa khách hàng thành công"}

# Lấy danh sách hóa đơn của khách hàng
@router.get("/{customer_id}/bills")
async def get_customer_bills(
    customer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách hóa đơn của khách hàng"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng"
        )
    
    # Kiểm tra quyền
    query = db.query(Bill).filter(Bill.customer_id == customer_id)
    
    if current_user.role == "agent":
        query = query.filter(Bill.agent_id == current_user.agent_id)
    
    # Áp dụng bộ lọc
    if status:
        query = query.filter(Bill.status == status)
    if from_date:
        query = query.filter(Bill.created_at >= from_date)
    if to_date:
        query = query.filter(Bill.created_at <= to_date)
    
    bills = query.order_by(desc(Bill.created_at)).offset(skip).limit(limit).all()
    total = query.count()
    
    return {
        "customer_id": customer_id,
        "customer_name": customer.customer_name,
        "total_bills": total,
        "bills": [
            {
                "id": bill.id,
                "bill_code": bill.bill_code,
                "period": bill.period,
                "total_amount": bill.total_amount,
                "status": bill.status,
                "sale_date": bill.sale_date,
                "payment_date": bill.payment_date,
                "created_at": bill.created_at
            }
            for bill in bills
        ]
    }

# Thống kê khách hàng
@router.get("/{customer_id}/stats", response_model=CustomerStats)
async def get_customer_stats(
    customer_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Thống kê chi tiết khách hàng"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng"
        )
    
    # Kiểm tra quyền
    query = db.query(Bill).filter(Bill.customer_id == customer_id)
    
    if current_user.role == "agent":
        query = query.filter(Bill.agent_id == current_user.agent_id)
    
    # Áp dụng bộ lọc thời gian
    if from_date:
        query = query.filter(Bill.created_at >= from_date)
    if to_date:
        query = query.filter(Bill.created_at <= to_date)
    
    # Tính toán thống kê
    total_bills = query.count()
    total_amount = query.with_entities(func.sum(Bill.total_amount)).scalar() or 0
    avg_amount = total_amount / total_bills if total_bills > 0 else 0
    
    # Thống kê theo trạng thái
    status_stats = db.query(
        Bill.status,
        func.count(Bill.id).label("count"),
        func.sum(Bill.total_amount).label("total")
    ).filter(
        Bill.customer_id == customer_id
    )
    
    if current_user.role == "agent":
        status_stats = status_stats.filter(Bill.agent_id == current_user.agent_id)
    
    if from_date:
        status_stats = status_stats.filter(Bill.created_at >= from_date)
    if to_date:
        status_stats = status_stats.filter(Bill.created_at <= to_date)
    
    status_stats = status_stats.group_by(Bill.status).all()
    
    # Thống kê theo kỳ (12 kỳ gần nhất)
    period_stats = db.query(
        Bill.period,
        func.count(Bill.id).label("count"),
        func.sum(Bill.total_amount).label("total"),
        func.avg(Bill.total_amount).label("average")
    ).filter(
        Bill.customer_id == customer_id
    )
    
    if current_user.role == "agent":
        period_stats = period_stats.filter(Bill.agent_id == current_user.agent_id)
    
    if from_date:
        period_stats = period_stats.filter(Bill.created_at >= from_date)
    if to_date:
        period_stats = period_stats.filter(Bill.created_at <= to_date)
    
    period_stats = period_stats.group_by(Bill.period).order_by(desc(Bill.period)).limit(12).all()
    
    # Thống kê theo tháng (12 tháng gần nhất)
    monthly_stats = db.query(
        func.date_format(Bill.created_at, '%Y-%m').label("month"),
        func.count(Bill.id).label("count"),
        func.sum(Bill.total_amount).label("total")
    ).filter(
        Bill.customer_id == customer_id
    )
    
    if current_user.role == "agent":
        monthly_stats = monthly_stats.filter(Bill.agent_id == current_user.agent_id)
    
    monthly_stats = monthly_stats.group_by(
        func.date_format(Bill.created_at, '%Y-%m')
    ).order_by(
        desc(func.date_format(Bill.created_at, '%Y-%m'))
    ).limit(12).all()
    
    return CustomerStats(
        customer_id=customer_id,
        customer_code=customer.customer_code,
        customer_name=customer.customer_name,
        total_bills=total_bills,
        total_amount=total_amount,
        average_amount=avg_amount,
        by_status={
            stat.status: {
                "count": stat.count,
                "total_amount": stat.total or 0
            }
            for stat in status_stats
        },
        by_period={
            stat.period: {
                "count": stat.count,
                "total_amount": stat.total or 0,
                "average_amount": stat.average or 0
            }
            for stat in period_stats
        },
        by_month={
            stat.month: {
                "count": stat.count,
                "total_amount": stat.total or 0
            }
            for stat in monthly_stats
        }
    )

# Tìm kiếm khách hàng nâng cao
@router.get("/search/advanced", response_model=CustomerSearchResponse)
async def advanced_search_customers(
    query_string: str = Query(..., min_length=2),
    search_fields: str = Query("all", regex="^(all|code|name|phone|email|address)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Tìm kiếm khách hàng nâng cao"""
    search_term = f"%{query_string}%"
    
    # Xây dựng query dựa trên trường tìm kiếm
    if search_fields == "code":
        query = db.query(Customer).filter(Customer.customer_code.ilike(search_term))
    elif search_fields == "name":
        query = db.query(Customer).filter(Customer.customer_name.ilike(search_term))
    elif search_fields == "phone":
        query = db.query(Customer).filter(Customer.phone.ilike(search_term))
    elif search_fields == "email":
        query = db.query(Customer).filter(Customer.email.ilike(search_term))
    elif search_fields == "address":
        query = db.query(Customer).filter(
            Customer.address.ilike(search_term) |
            Customer.province.ilike(search_term) |
            Customer.district.ilike(search_term) |
            Customer.ward.ilike(search_term)
        )
    else:  # all
        query = db.query(Customer).filter(
            Customer.customer_code.ilike(search_term) |
            Customer.customer_name.ilike(search_term) |
            Customer.phone.ilike(search_term) |
            Customer.email.ilike(search_term) |
            Customer.address.ilike(search_term) |
            Customer.province.ilike(search_term) |
            Customer.district.ilike(search_term) |
            Customer.ward.ilike(search_term)
        )
    
    # Phân quyền: Đại lý chỉ xem được khách hàng có hóa đơn của mình
    if current_user.role == "agent":
        agent_bills = db.query(Bill.customer_id).filter(
            Bill.agent_id == current_user.agent_id
        ).distinct().all()
        
        customer_ids = [bill[0] for bill in agent_bills]
        if customer_ids:
            query = query.filter(Customer.id.in_(customer_ids))
        else:
            query = query.filter(Customer.id == 0)
    
    # Thực hiện tìm kiếm
    customers = query.order_by(desc(Customer.created_at)).limit(50).all()
    total = query.count()
    
    return CustomerSearchResponse(
        query=query_string,
        search_fields=search_fields,
        total_results=total,
        results=[CustomerResponse.from_orm(customer) for customer in customers]
    )

# Import khách hàng từ file
@router.post("/import")
async def import_customers(
    file_content: str,
    format: str = Query("csv", regex="^(csv|json)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import khách hàng từ file"""
    try:
        customers_data = []
        
        if format == "csv":
            # Parse CSV
            lines = file_content.strip().split('\n')
            if len(lines) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File CSV không có dữ liệu"
                )
            
            headers = lines[0].split(',')
            required_headers = ['customer_code', 'customer_name', 'phone']
            
            for header in required_headers:
                if header not in headers:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Thiếu header bắt buộc: {header}"
                    )
            
            for line in lines[1:]:
                values = line.split(',')
                if len(values) >= 3:
                    customer_data = {
                        'customer_code': values[headers.index('customer_code')].strip(),
                        'customer_name': values[headers.index('customer_name')].strip(),
                        'phone': values[headers.index('phone')].strip(),
                        'email': values[headers.index('email')].strip() if 'email' in headers else None,
                        'address': values[headers.index('address')].strip() if 'address' in headers else None,
                        'province': values[headers.index('province')].strip() if 'province' in headers else None,
                        'district': values[headers.index('district')].strip() if 'district' in headers else None,
                        'ward': values[headers.index('ward')].strip() if 'ward' in headers else None
                    }
                    customers_data.append(customer_data)
        
        elif format == "json":
            # Parse JSON
            try:
                customers_data = json.loads(file_content)
                if not isinstance(customers_data, list):
                    customers_data = [customers_data]
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File JSON không hợp lệ"
                )
        
        # Import khách hàng
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, data in enumerate(customers_data):
            try:
                # Kiểm tra dữ liệu bắt buộc
                if not data.get('customer_code') or not data.get('customer_name') or not data.get('phone'):
                    raise ValueError("Thiếu thông tin bắt buộc")
                
                # Kiểm tra mã khách hàng đã tồn tại
                existing = db.query(Customer).filter(
                    Customer.customer_code == data['customer_code']
                ).first()
                
                if existing:
                    # Cập nhật thông tin nếu đã tồn tại
                    update_data = {k: v for k, v in data.items() if v is not None}
                    for field, value in update_data.items():
                        if hasattr(existing, field):
                            setattr(existing, field, value)
                    
                    existing.updated_at = datetime.now()
                    existing.updated_by = current_user.id
                    db.commit()
                    success_count += 1
                else:
                    # Tạo mới
                    customer = Customer(
                        **data,
                        created_by=current_user.id
                    )
                    db.add(customer)
                    db.commit()
                    success_count += 1
                    
            except Exception as e:
                error_count += 1
                errors.append(f"Dòng {idx + 1}: {str(e)}")
        
        return {
            "message": "Import khách hàng hoàn tất",
            "total": len(customers_data),
            "success": success_count,
            "failed": error_count,
            "errors": errors[:10]  # Chỉ trả về 10 lỗi đầu
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi khi import file: {str(e)}"
        )

# Xuất danh sách khách hàng
@router.get("/export")
async def export_customers(
    format: str = Query("csv", regex="^(csv|excel)$"),
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xuất danh sách khách hàng"""
    query = db.query(Customer)
    
    # Áp dụng bộ lọc
    if status:
        query = query.filter(Customer.status == status)
    if from_date:
        query = query.filter(Customer.created_at >= from_date)
    if to_date:
        query = query.filter(Customer.created_at <= to_date)
    
    # Phân quyền
    if current_user.role == "agent":
        agent_bills = db.query(Bill.customer_id).filter(
            Bill.agent_id == current_user.agent_id
        ).distinct().all()
        
        customer_ids = [bill[0] for bill in agent_bills]
        if customer_ids:
            query = query.filter(Customer.id.in_(customer_ids))
        else:
            query = query.filter(Customer.id == 0)
    
    customers = query.order_by(desc(Customer.created_at)).all()
    
    # Chuẩn bị dữ liệu
    data = []
    for customer in customers:
        # Đếm số hóa đơn
        bill_count = db.query(Bill).filter(Bill.customer_id == customer.id).count()
        
        data.append({
            "Mã KH": customer.customer_code,
            "Tên KH": customer.customer_name,
            "SĐT": customer.phone or "",
            "Email": customer.email or "",
            "Địa chỉ": customer.address or "",
            "Tỉnh/TP": customer.province or "",
            "Quận/Huyện": customer.district or "",
            "Phường/Xã": customer.ward or "",
            "Số hóa đơn": bill_count,
            "Trạng thái": customer.status,
            "Ngày tạo": customer.created_at.strftime("%d/%m/%Y %H:%M:%S")
        })
    
    # Tạo file CSV
    if format == "csv":
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không có dữ liệu để xuất"
            )
        
        headers = data[0].keys()
        csv_lines = [",".join(headers)]
        
        for row in data:
            csv_lines.append(",".join([
                f'"{str(value)}"' for value in row.values()
            ]))
        
        return {
            "filename": f"customers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "content": "\n".join(csv_lines),
            "format": "text/csv"
        }
    
    else:  # excel
        return {
            "filename": f"customers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "message": "Excel export chưa được triển khai. Vui lòng sử dụng CSV.",
            "format": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }

# Lấy danh sách khách hàng thường xuyên
@router.get("/frequent")
async def get_frequent_customers(
    limit: int = Query(20, ge=1, le=100),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách khách hàng thường xuyên (có nhiều hóa đơn nhất)"""
    # Query để đếm số hóa đơn theo khách hàng
    subquery = db.query(
        Bill.customer_id,
        func.count(Bill.id).label('bill_count'),
        func.sum(Bill.total_amount).label('total_amount'),
        func.max(Bill.created_at).label('last_bill_date')
    )
    
    if from_date:
        subquery = subquery.filter(Bill.created_at >= from_date)
    if to_date:
        subquery = subquery.filter(Bill.created_at <= to_date)
    
    # Phân quyền
    if current_user.role == "agent":
        subquery = subquery.filter(Bill.agent_id == current_user.agent_id)
    
    subquery = subquery.group_by(Bill.customer_id).subquery()
    
    # Join với bảng Customer
    query = db.query(
        Customer,
        subquery.c.bill_count,
        subquery.c.total_amount,
        subquery.c.last_bill_date
    ).join(
        subquery,
        Customer.id == subquery.c.customer_id
    ).order_by(
        desc(subquery.c.bill_count)
    ).limit(limit)
    
    results = query.all()
    
    return {
        "from_date": from_date,
        "to_date": to_date,
        "customers": [
            {
                "customer": CustomerResponse.from_orm(result[0]),
                "bill_count": result[1],
                "total_amount": result[2] or 0,
                "last_bill_date": result[3],
                "average_amount": (result[2] or 0) / result[1] if result[1] > 0 else 0
            }
            for result in results
        ]
    }