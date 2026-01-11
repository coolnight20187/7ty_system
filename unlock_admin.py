"""
Script to unlock admin account and verify password
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Configure database connection
DB_HOST = os.getenv("DB_HOST", "7ty_postgres")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "7ty_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "7ty_password_secure")
DB_NAME = os.getenv("DB_NAME", "7ty_vn_db")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Import models and security utils
from models import User
from utils import SecurityUtils

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def unlock_admin():
    """Unlock admin account and verify password"""
    db = SessionLocal()
    try:
        # Find admin user
        admin = db.query(User).filter(User.username == "admin").first()
        
        if not admin:
            print("❌ Admin user not found!")
            return
        
        print(f"Current admin status:")
        print(f"  Username: {admin.username}")
        print(f"  Email: {admin.email}")
        print(f"  Is Active: {admin.is_active}")
        print(f"  Login Attempts: {admin.login_attempts}")
        print(f"  Locked Until: {admin.locked_until}")
        print(f"  Password Hash: {admin.password_hash[:50]}...")
        
        # Test password verification
        test_password = "Admin@12345"
        print(f"\nTesting password verification with: {test_password}")
        
        try:
            is_valid = SecurityUtils.verify_password(test_password, admin.password_hash)
            print(f"  Password verification result: {is_valid}")
        except Exception as e:
            print(f"  ❌ Password verification error: {e}")
        
        # Unlock account
        print(f"\nUnlocking account...")
        admin.is_active = True
        admin.login_attempts = 0
        admin.locked_until = None
        
        db.commit()
        print(f"✅ Admin account unlocked!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    unlock_admin()
