"""
Migration script: Thêm các trường cho hệ thống Tài Khoản Tập Trung
- account_type: Loại tài khoản (SYSTEM, AGENT, STAFF, CUSTOMER)
- account_status: Trạng thái tài khoản (ACTIVE, PENDING, INACTIVE, SUSPENDED, BLOCKED)
- is_admin, is_manager, is_agent, is_staff, is_customer: Đa vai trò
- active_role: Vai trò đang hoạt động
"""

import os
import sys
import psycopg2
from psycopg2 import sql

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

def run_migration():
    """Run migration to add unified account fields"""
    
    print("=" * 60)
    print("MIGRATION: Hệ thống Tài Khoản Tập Trung")
    print("=" * 60)
    
    conn = None
    try:
        # Connect to database
        print("\n[1] Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Create ENUM types if not exist
        print("\n[2] Creating ENUM types...")
        
        # AccountType enum
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'accounttype') THEN
                    CREATE TYPE accounttype AS ENUM ('SYSTEM', 'AGENT', 'STAFF', 'CUSTOMER');
                END IF;
            END$$;
        """)
        print("   ✓ accounttype ENUM created")
        
        # AccountStatus enum
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'accountstatus') THEN
                    CREATE TYPE accountstatus AS ENUM ('ACTIVE', 'PENDING', 'INACTIVE', 'SUSPENDED', 'BLOCKED');
                END IF;
            END$$;
        """)
        print("   ✓ accountstatus ENUM created")
        
        # Add columns to users table
        print("\n[3] Adding columns to users table...")
        
        columns_to_add = [
            ("account_type", "accounttype", "'CUSTOMER'::accounttype"),
            ("account_status", "accountstatus", "'PENDING'::accountstatus"),
            ("is_admin", "BOOLEAN", "FALSE"),
            ("is_manager", "BOOLEAN", "FALSE"),
            ("is_agent", "BOOLEAN", "FALSE"),
            ("is_customer", "BOOLEAN", "FALSE"),
            ("active_role", "userrole", "NULL"),
        ]
        
        for col_name, col_type, default_value in columns_to_add:
            try:
                cur.execute(f"""
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type} DEFAULT {default_value};
                """)
                print(f"   ✓ Column '{col_name}' added")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"   - Column '{col_name}' already exists")
                else:
                    print(f"   ✗ Error adding '{col_name}': {e}")
        
        # Migrate existing data
        print("\n[4] Migrating existing data...")
        
        # Update account_type and role flags based on existing role
        cur.execute("""
            UPDATE users SET 
                account_type = CASE 
                    WHEN role IN ('ADMIN', 'MANAGER') THEN 'SYSTEM'::accounttype
                    WHEN role = 'AGENT' THEN 'AGENT'::accounttype
                    WHEN role = 'STAFF' THEN 'STAFF'::accounttype
                    WHEN role = 'CUSTOMER' THEN 'CUSTOMER'::accounttype
                    ELSE 'CUSTOMER'::accounttype
                END,
                account_status = CASE 
                    WHEN is_active = TRUE THEN 'ACTIVE'::accountstatus
                    ELSE 'INACTIVE'::accountstatus
                END,
                is_admin = CASE WHEN role = 'ADMIN' THEN TRUE ELSE FALSE END,
                is_manager = CASE WHEN role = 'MANAGER' THEN TRUE ELSE FALSE END,
                is_agent = CASE WHEN role = 'AGENT' THEN TRUE ELSE is_agent END,
                is_customer = CASE WHEN role = 'CUSTOMER' THEN TRUE ELSE FALSE END
            WHERE account_type IS NULL OR account_status IS NULL;
        """)
        print(f"   ✓ Updated existing users with role flags")
        
        # Update users who have agent records
        cur.execute("""
            UPDATE users u SET 
                is_agent = TRUE,
                account_type = 'AGENT'::accounttype
            FROM agents a 
            WHERE a.user_id = u.id 
            AND u.is_agent = FALSE;
        """)
        print("   ✓ Synced is_agent flag with agents table")
        
        # Update users who have staff records
        cur.execute("""
            UPDATE users u SET 
                is_staff = TRUE
            FROM staffs s 
            WHERE s.user_id = u.id 
            AND u.is_staff = FALSE;
        """)
        print("   ✓ Synced is_staff flag with staffs table")
        
        # Update users who have customer records
        cur.execute("""
            UPDATE users u SET 
                is_customer = TRUE
            FROM customers c 
            WHERE c.user_id = u.id 
            AND u.is_customer = FALSE;
        """)
        print("   ✓ Synced is_customer flag with customers table")
        
        # Add indexes
        print("\n[5] Creating indexes...")
        
        indexes = [
            ("idx_user_account_type", "account_type"),
            ("idx_user_account_status", "account_status"),
            ("idx_user_is_admin", "is_admin"),
            ("idx_user_is_agent", "is_agent"),
            ("idx_user_is_staff", "is_staff"),
            ("idx_user_is_customer", "is_customer"),
        ]
        
        for idx_name, col_name in indexes:
            try:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name} ON users ({col_name});
                """)
                print(f"   ✓ Index '{idx_name}' created")
            except Exception as e:
                print(f"   - Index '{idx_name}': {e}")
        
        # Commit transaction
        conn.commit()
        
        # Display summary
        print("\n[6] Migration Summary...")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_admin THEN 1 ELSE 0 END) as admins,
                SUM(CASE WHEN is_manager THEN 1 ELSE 0 END) as managers,
                SUM(CASE WHEN is_agent THEN 1 ELSE 0 END) as agents,
                SUM(CASE WHEN is_staff THEN 1 ELSE 0 END) as staffs,
                SUM(CASE WHEN is_customer THEN 1 ELSE 0 END) as customers
            FROM users;
        """)
        result = cur.fetchone()
        
        print(f"""
   ┌─────────────────────────────────────────┐
   │     HỆ THỐNG TÀI KHOẢN TẬP TRUNG       │
   ├─────────────────────────────────────────┤
   │  Tổng tài khoản:     {result[0]:>10}         │
   │  ─────────────────────────────────────  │
   │  Quản trị (Admin):   {result[1]:>10}         │
   │  Quản lý (Manager):  {result[2]:>10}         │
   │  Đại lý (Agent):     {result[3]:>10}         │
   │  Nhân viên (Staff):  {result[4]:>10}         │
   │  Khách hàng (KH):    {result[5]:>10}         │
   └─────────────────────────────────────────┘
        """)
        
        print("\n✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ MIGRATION ERROR: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration()
