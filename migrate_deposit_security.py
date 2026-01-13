"""
Migration script cho hệ thống nạp tiền bảo mật
Tạo các bảng:
- deposit_requests
- deposit_limits
- deposit_security_logs
- system_bank_accounts
"""

import sys
from sqlalchemy import text, inspect
from database import engine, SessionLocal
from models import Base, DepositRequest, DepositLimit, DepositSecurityLog, SystemBankAccount
import json
from pathlib import Path

def run_migration():
    """Chạy migration tạo bảng mới"""
    print("=" * 50)
    print("DEPOSIT SECURITY MIGRATION")
    print("=" * 50)
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    tables_to_create = [
        ("deposit_requests", DepositRequest),
        ("deposit_limits", DepositLimit),
        ("deposit_security_logs", DepositSecurityLog),
        ("system_bank_accounts", SystemBankAccount)
    ]
    
    for table_name, model in tables_to_create:
        if table_name in existing_tables:
            print(f"✓ Table '{table_name}' already exists")
        else:
            try:
                model.__table__.create(engine)
                print(f"✓ Created table '{table_name}'")
            except Exception as e:
                print(f"✗ Error creating '{table_name}': {e}")
    
    # Migrate bank accounts from JSON file
    migrate_bank_accounts_from_json()
    
    # Create default deposit limit
    create_default_deposit_limit()
    
    print("\n" + "=" * 50)
    print("MIGRATION COMPLETED")
    print("=" * 50)

def migrate_bank_accounts_from_json():
    """Migrate bank accounts from JSON file to database"""
    json_file = Path("data/system_bank_accounts.json")
    
    if not json_file.exists():
        print("\n⚠ No bank accounts JSON file found")
        return
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            accounts = json.load(f)
    except Exception as e:
        print(f"\n✗ Error reading JSON: {e}")
        return
    
    if not accounts:
        print("\n⚠ No bank accounts to migrate")
        return
    
    db = SessionLocal()
    try:
        # Check if already migrated
        existing = db.query(SystemBankAccount).count()
        if existing > 0:
            print(f"\n✓ Bank accounts already migrated ({existing} accounts)")
            return
        
        print(f"\nMigrating {len(accounts)} bank accounts from JSON...")
        
        for i, acc in enumerate(accounts):
            bank_account = SystemBankAccount(
                bank_name=acc.get("bank_name", ""),
                bank_full_name=acc.get("bank_full_name"),
                account_number=acc.get("account_number", ""),
                account_name=acc.get("account_name", ""),
                branch=acc.get("branch"),
                is_active=acc.get("is_active", True),
                is_default=(i == 0),  # First one is default
                priority=i,
                qr_code=acc.get("qr_code"),
                notes=acc.get("notes")
            )
            db.add(bank_account)
        
        db.commit()
        print(f"✓ Migrated {len(accounts)} bank accounts")
        
    except Exception as e:
        print(f"✗ Error migrating bank accounts: {e}")
        db.rollback()
    finally:
        db.close()

def create_default_deposit_limit():
    """Tạo giới hạn nạp tiền mặc định"""
    db = SessionLocal()
    try:
        existing = db.query(DepositLimit).filter(DepositLimit.agent_id.is_(None)).first()
        if existing:
            print("\n✓ Default deposit limit already exists")
            return
        
        default_limit = DepositLimit(
            agent_id=None,  # Global default
            min_amount=100000,           # 100k
            max_amount=100000000,        # 100M
            daily_limit=500000000,       # 500M/day
            monthly_limit=5000000000,    # 5B/month
            max_daily_count=10,
            max_hourly_count=3,
            require_otp=True,
            require_admin_approval=False,
            approval_threshold=50000000,  # 50M cần duyệt
            is_active=True
        )
        db.add(default_limit)
        db.commit()
        print("\n✓ Created default deposit limit")
        
    except Exception as e:
        print(f"\n✗ Error creating default limit: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
