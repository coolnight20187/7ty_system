"""
Reward Points System Router
Quản lý hệ thống điểm thưởng cho Đại lý
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
import uuid

from database import get_db
from dependencies import get_current_user, get_current_active_user, admin_only
from models import (
    User, UserRole, Agent, Transaction, TransactionType, TransactionStatus,
    RewardProgram, RewardProgramType, RewardTransaction
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Rewards"])


# ==================== REWARD PROGRAMS CRUD ====================

@router.get("/programs", response_model=Dict[str, Any])
def get_reward_programs(
    is_active: Optional[bool] = None,
    program_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all reward programs"""
    try:
        query = db.query(RewardProgram)
        
        if is_active is not None:
            query = query.filter(RewardProgram.is_active == is_active)
        
        if program_type:
            query = query.filter(RewardProgram.program_type == program_type)
        
        programs = query.order_by(RewardProgram.priority.desc(), RewardProgram.id).all()
        
        return {
            "success": True,
            "data": [{
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "description": p.description,
                "program_type": p.program_type.value if p.program_type else None,
                "points_amount": p.points_amount,
                "points_percentage": float(p.points_percentage) if p.points_percentage else 0,
                "min_amount": float(p.min_amount) if p.min_amount else 0,
                "max_points": p.max_points,
                "multiplier": float(p.multiplier) if p.multiplier else 1,
                "is_active": p.is_active,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "icon": p.icon,
                "color": p.color,
                "priority": p.priority,
                "daily_limit": p.daily_limit,
                "monthly_limit": p.monthly_limit
            } for p in programs],
            "total": len(programs)
        }
        
    except Exception as e:
        logger.error(f"Error getting reward programs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/programs/{program_id}", response_model=Dict[str, Any])
def get_reward_program(
    program_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific reward program"""
    program = db.query(RewardProgram).filter(RewardProgram.id == program_id).first()
    
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chương trình thưởng"
        )
    
    return {
        "success": True,
        "data": {
            "id": program.id,
            "code": program.code,
            "name": program.name,
            "description": program.description,
            "program_type": program.program_type.value,
            "points_amount": program.points_amount,
            "points_percentage": float(program.points_percentage),
            "min_amount": float(program.min_amount),
            "max_points": program.max_points,
            "min_transactions": program.min_transactions,
            "min_deposit": float(program.min_deposit),
            "required_days": program.required_days,
            "multiplier": float(program.multiplier),
            "daily_limit": program.daily_limit,
            "monthly_limit": program.monthly_limit,
            "total_limit": program.total_limit,
            "is_active": program.is_active,
            "start_date": program.start_date.isoformat() if program.start_date else None,
            "end_date": program.end_date.isoformat() if program.end_date else None,
            "icon": program.icon,
            "color": program.color,
            "priority": program.priority
        }
    }


@router.post("/programs/{program_id}/toggle", response_model=Dict[str, Any])
@admin_only()
def toggle_reward_program(
    program_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle a reward program on/off"""
    program = db.query(RewardProgram).filter(RewardProgram.id == program_id).first()
    
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chương trình thưởng"
        )
    
    program.is_active = not program.is_active
    program.updated_at = datetime.utcnow()
    db.commit()
    
    status_text = "Đã bật" if program.is_active else "Đã tắt"
    logger.info(f"Reward program {program.code} toggled to {program.is_active} by {current_user.username}")
    
    return {
        "success": True,
        "message": f"{status_text} chương trình {program.name}",
        "data": {
            "id": program.id,
            "code": program.code,
            "is_active": program.is_active
        }
    }


@router.put("/programs/{program_id}", response_model=Dict[str, Any])
@admin_only()
def update_reward_program(
    program_id: int,
    update_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a reward program"""
    program = db.query(RewardProgram).filter(RewardProgram.id == program_id).first()
    
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chương trình thưởng"
        )
    
    # Update allowed fields
    allowed_fields = [
        'name', 'description', 'points_amount', 'points_percentage',
        'min_amount', 'max_points', 'min_transactions', 'min_deposit',
        'required_days', 'multiplier', 'daily_limit', 'monthly_limit',
        'total_limit', 'is_active', 'start_date', 'end_date', 'icon', 
        'color', 'priority'
    ]
    
    for field in allowed_fields:
        if field in update_data:
            value = update_data[field]
            if field in ['start_date', 'end_date'] and value:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            setattr(program, field, value)
    
    program.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"Reward program {program.code} updated by {current_user.username}")
    
    return {
        "success": True,
        "message": f"Đã cập nhật chương trình {program.name}",
        "data": {"id": program.id, "code": program.code}
    }


# ==================== AGENT REWARD POINTS ====================

@router.get("/agents/{agent_id}/points", response_model=Dict[str, Any])
def get_agent_points(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get agent's reward points summary"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đại lý"
        )
    
    # Get recent transactions
    recent_transactions = db.query(RewardTransaction).filter(
        RewardTransaction.agent_id == agent_id
    ).order_by(desc(RewardTransaction.created_at)).limit(10).all()
    
    return {
        "success": True,
        "data": {
            "agent_id": agent.id,
            "agent_code": agent.agent_code,
            "current_points": agent.reward_points,
            "total_earned": agent.total_points_earned,
            "total_redeemed": agent.total_points_redeemed,
            "vip_tier": agent.vip_tier,
            "recent_transactions": [{
                "id": t.id,
                "transaction_code": t.transaction_code,
                "points": t.points,
                "points_type": t.points_type,
                "description": t.description,
                "created_at": t.created_at.isoformat()
            } for t in recent_transactions]
        }
    }


@router.get("/agents/{agent_id}/transactions", response_model=Dict[str, Any])
def get_agent_reward_transactions(
    agent_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    points_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get agent's reward transaction history"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đại lý"
        )
    
    query = db.query(RewardTransaction).filter(RewardTransaction.agent_id == agent_id)
    
    if points_type:
        query = query.filter(RewardTransaction.points_type == points_type)
    
    total = query.count()
    transactions = query.order_by(desc(RewardTransaction.created_at))\
        .offset((page - 1) * limit).limit(limit).all()
    
    return {
        "success": True,
        "data": [{
            "id": t.id,
            "transaction_code": t.transaction_code,
            "points": t.points,
            "points_type": t.points_type,
            "previous_balance": t.previous_balance,
            "new_balance": t.new_balance,
            "description": t.description,
            "program": t.program.name if t.program else None,
            "created_at": t.created_at.isoformat()
        } for t in transactions],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.post("/agents/{agent_id}/add-points", response_model=Dict[str, Any])
@admin_only()
def add_points_to_agent(
    agent_id: int,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually add points to agent (admin only)"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đại lý"
        )
    
    points = data.get('points', 0)
    description = data.get('description', 'Điều chỉnh thủ công bởi Admin')
    
    if points == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điểm phải khác 0"
        )
    
    # Create reward transaction
    prev_balance = agent.reward_points
    agent.reward_points += points
    
    if points > 0:
        agent.total_points_earned += points
        points_type = "earn"
    else:
        agent.total_points_redeemed += abs(points)
        points_type = "adjust"
    
    reward_tx = RewardTransaction(
        agent_id=agent_id,
        transaction_code=f"RWD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
        points=points,
        points_type=points_type,
        previous_balance=prev_balance,
        new_balance=agent.reward_points,
        description=description,
        reference_type="manual",
        created_by_id=current_user.id
    )
    
    db.add(reward_tx)
    db.commit()
    
    logger.info(f"Added {points} points to agent {agent.agent_code} by {current_user.username}")
    
    return {
        "success": True,
        "message": f"Đã {'cộng' if points > 0 else 'trừ'} {abs(points)} điểm cho {agent.agent_code}",
        "data": {
            "previous_balance": prev_balance,
            "new_balance": agent.reward_points,
            "transaction_code": reward_tx.transaction_code
        }
    }


# ==================== REWARD PROCESSING ====================

def generate_reward_tx_code():
    """Generate unique reward transaction code"""
    return f"RWD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def process_reward_for_deposit(db: Session, agent: Agent, amount: Decimal, transaction_id: int = None):
    """Process rewards for deposit transaction"""
    try:
        # Get active deposit bonus programs
        programs = db.query(RewardProgram).filter(
            RewardProgram.is_active == True,
            RewardProgram.program_type.in_([
                RewardProgramType.DEPOSIT_BONUS,
                RewardProgramType.FIRST_DEPOSIT
            ])
        ).all()
        
        total_points = 0
        
        for program in programs:
            # Check if amount meets minimum
            if amount < program.min_amount:
                continue
            
            # Check date range
            now = datetime.utcnow()
            if program.start_date and now < program.start_date:
                continue
            if program.end_date and now > program.end_date:
                continue
            
            # Calculate points
            if program.points_percentage > 0:
                points = int(float(amount) * float(program.points_percentage) / 100)
            else:
                points = program.points_amount
            
            # Apply multiplier
            points = int(points * float(program.multiplier))
            
            # Apply max limit
            if program.max_points and points > program.max_points:
                points = program.max_points
            
            if points > 0:
                # Create reward transaction
                prev_balance = agent.reward_points
                agent.reward_points += points
                agent.total_points_earned += points
                
                reward_tx = RewardTransaction(
                    agent_id=agent.id,
                    program_id=program.id,
                    transaction_id=transaction_id,
                    transaction_code=generate_reward_tx_code(),
                    points=points,
                    points_type="earn",
                    previous_balance=prev_balance,
                    new_balance=agent.reward_points,
                    description=f"{program.name}: Nạp {amount:,.0f}đ",
                    reference_type="deposit",
                    reference_id=transaction_id
                )
                db.add(reward_tx)
                total_points += points
                
                logger.info(f"Agent {agent.agent_code} earned {points} points from {program.code}")
        
        return total_points
        
    except Exception as e:
        logger.error(f"Error processing deposit reward: {e}")
        return 0


def process_reward_for_transaction(db: Session, agent: Agent, amount: Decimal, tx_type: str, transaction_id: int = None):
    """Process rewards for bill payment transaction"""
    try:
        programs = db.query(RewardProgram).filter(
            RewardProgram.is_active == True,
            RewardProgram.program_type == RewardProgramType.TRANSACTION_BONUS
        ).all()
        
        total_points = 0
        
        for program in programs:
            if amount < program.min_amount:
                continue
            
            now = datetime.utcnow()
            if program.start_date and now < program.start_date:
                continue
            if program.end_date and now > program.end_date:
                continue
            
            if program.points_percentage > 0:
                points = int(float(amount) * float(program.points_percentage) / 100)
            else:
                points = program.points_amount
            
            points = int(points * float(program.multiplier))
            
            if program.max_points and points > program.max_points:
                points = program.max_points
            
            if points > 0:
                prev_balance = agent.reward_points
                agent.reward_points += points
                agent.total_points_earned += points
                
                reward_tx = RewardTransaction(
                    agent_id=agent.id,
                    program_id=program.id,
                    transaction_id=transaction_id,
                    transaction_code=generate_reward_tx_code(),
                    points=points,
                    points_type="earn",
                    previous_balance=prev_balance,
                    new_balance=agent.reward_points,
                    description=f"{program.name}: Giao dịch {amount:,.0f}đ",
                    reference_type="transaction",
                    reference_id=transaction_id
                )
                db.add(reward_tx)
                total_points += points
        
        return total_points
        
    except Exception as e:
        logger.error(f"Error processing transaction reward: {e}")
        return 0


# ==================== STATS & LEADERBOARD ====================

@router.get("/stats", response_model=Dict[str, Any])
@admin_only()
def get_reward_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overall reward system statistics"""
    try:
        # Total points issued
        total_earned = db.query(func.sum(Agent.total_points_earned)).scalar() or 0
        total_redeemed = db.query(func.sum(Agent.total_points_redeemed)).scalar() or 0
        total_current = db.query(func.sum(Agent.reward_points)).scalar() or 0
        
        # Active programs
        active_programs = db.query(func.count(RewardProgram.id)).filter(
            RewardProgram.is_active == True
        ).scalar() or 0
        
        # Transactions today
        today = date.today()
        today_transactions = db.query(func.count(RewardTransaction.id)).filter(
            func.date(RewardTransaction.created_at) == today
        ).scalar() or 0
        
        today_points = db.query(func.sum(RewardTransaction.points)).filter(
            func.date(RewardTransaction.created_at) == today,
            RewardTransaction.points_type == "earn"
        ).scalar() or 0
        
        # Top agents by points
        top_agents = db.query(Agent).order_by(desc(Agent.reward_points)).limit(10).all()
        
        return {
            "success": True,
            "data": {
                "total_points_earned": total_earned,
                "total_points_redeemed": total_redeemed,
                "total_current_points": total_current,
                "active_programs": active_programs,
                "today_transactions": today_transactions,
                "today_points": today_points,
                "top_agents": [{
                    "agent_id": a.id,
                    "agent_code": a.agent_code,
                    "agent_name": a.user.full_name if a.user else a.agent_name,
                    "reward_points": a.reward_points,
                    "vip_tier": a.vip_tier
                } for a in top_agents]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting reward stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== INITIALIZE DEFAULT PROGRAMS ====================

@router.post("/initialize-programs", response_model=Dict[str, Any])
@admin_only()
def initialize_reward_programs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initialize 10 default reward programs"""
    try:
        # Check if already initialized
        existing = db.query(RewardProgram).count()
        if existing > 0:
            return {
                "success": False,
                "message": f"Đã có {existing} chương trình thưởng. Không cần khởi tạo lại.",
                "data": {"existing_count": existing}
            }
        
        # 10 Default reward programs
        default_programs = [
            {
                "code": "REG_BONUS",
                "name": "🎉 Thưởng Đăng Ký Mới",
                "description": "Đại lý mới đăng ký nhận ngay điểm thưởng chào mừng",
                "program_type": RewardProgramType.REGISTRATION,
                "points_amount": 500,
                "points_percentage": 0,
                "is_active": False,
                "icon": "fas fa-user-plus",
                "color": "#28a745",
                "priority": 10
            },
            {
                "code": "FIRST_DEPOSIT",
                "name": "💰 Thưởng Nạp Tiền Lần Đầu",
                "description": "Thưởng 2% điểm cho lần nạp tiền đầu tiên",
                "program_type": RewardProgramType.FIRST_DEPOSIT,
                "points_amount": 0,
                "points_percentage": Decimal("2.0"),
                "min_amount": Decimal("100000"),
                "max_points": 10000,
                "is_active": False,
                "icon": "fas fa-hand-holding-usd",
                "color": "#ffc107",
                "priority": 9
            },
            {
                "code": "DEPOSIT_BONUS",
                "name": "💵 Thưởng Nạp Tiền",
                "description": "Thưởng 0.5% điểm cho mỗi lần nạp tiền từ 500,000đ",
                "program_type": RewardProgramType.DEPOSIT_BONUS,
                "points_amount": 0,
                "points_percentage": Decimal("0.5"),
                "min_amount": Decimal("500000"),
                "max_points": 5000,
                "daily_limit": 3,
                "is_active": False,
                "icon": "fas fa-money-bill-wave",
                "color": "#17a2b8",
                "priority": 8
            },
            {
                "code": "TX_BONUS",
                "name": "📊 Thưởng Giao Dịch",
                "description": "Thưởng 0.1% điểm cho mỗi giao dịch thành công",
                "program_type": RewardProgramType.TRANSACTION_BONUS,
                "points_amount": 0,
                "points_percentage": Decimal("0.1"),
                "min_amount": Decimal("50000"),
                "max_points": 1000,
                "is_active": False,
                "icon": "fas fa-exchange-alt",
                "color": "#6f42c1",
                "priority": 7
            },
            {
                "code": "MONTHLY_SALES",
                "name": "📈 Thưởng Doanh Số Tháng",
                "description": "Thưởng điểm khi đạt doanh số 50 triệu/tháng",
                "program_type": RewardProgramType.MONTHLY_SALES,
                "points_amount": 5000,
                "min_amount": Decimal("50000000"),
                "monthly_limit": 1,
                "is_active": False,
                "icon": "fas fa-chart-line",
                "color": "#fd7e14",
                "priority": 6
            },
            {
                "code": "REFERRAL",
                "name": "👥 Thưởng Giới Thiệu",
                "description": "Thưởng 1000 điểm khi giới thiệu đại lý mới",
                "program_type": RewardProgramType.REFERRAL,
                "points_amount": 1000,
                "is_active": False,
                "icon": "fas fa-users",
                "color": "#20c997",
                "priority": 5
            },
            {
                "code": "BIRTHDAY",
                "name": "🎂 Thưởng Sinh Nhật",
                "description": "Thưởng 500 điểm vào ngày sinh nhật đại lý",
                "program_type": RewardProgramType.BIRTHDAY,
                "points_amount": 500,
                "is_active": False,
                "icon": "fas fa-birthday-cake",
                "color": "#e83e8c",
                "priority": 4
            },
            {
                "code": "LOYALTY_30",
                "name": "⭐ Thưởng Trung Thành 30 Ngày",
                "description": "Thưởng điểm cho đại lý hoạt động liên tục 30 ngày",
                "program_type": RewardProgramType.LOYALTY,
                "points_amount": 2000,
                "required_days": 30,
                "monthly_limit": 1,
                "is_active": False,
                "icon": "fas fa-medal",
                "color": "#6c757d",
                "priority": 3
            },
            {
                "code": "HOLIDAY_TET",
                "name": "🧧 Thưởng Tết Nguyên Đán",
                "description": "Thưởng điểm x2 trong dịp Tết Nguyên Đán",
                "program_type": RewardProgramType.HOLIDAY,
                "points_amount": 0,
                "multiplier": Decimal("2.0"),
                "is_active": False,
                "icon": "fas fa-gift",
                "color": "#dc3545",
                "priority": 2
            },
            {
                "code": "VIP_GOLD",
                "name": "👑 Thưởng Hạng Vàng",
                "description": "Thưởng 3000 điểm khi đạt hạng Vàng (tổng 100,000 điểm)",
                "program_type": RewardProgramType.VIP_TIER,
                "points_amount": 3000,
                "min_transactions": 100,
                "is_active": False,
                "icon": "fas fa-crown",
                "color": "#ffc107",
                "priority": 1
            }
        ]
        
        for prog_data in default_programs:
            program = RewardProgram(
                **prog_data,
                created_by_id=current_user.id
            )
            db.add(program)
        
        db.commit()
        
        logger.info(f"Initialized 10 reward programs by {current_user.username}")
        
        return {
            "success": True,
            "message": "Đã khởi tạo 10 chương trình thưởng mặc định",
            "data": {"created_count": 10}
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing reward programs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
