"""
Script to reset admin user password
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

def reset_admin_password():
    """Reset admin user password"""
    db = SessionLocal()
    try:
        # Find admin user
        admin = db.query(User).filter(User.username == "admin").first()
        
        if not admin:
            print("❌ Admin user not found!")
            return
        
        # Set new password
        new_password = "Admin@12345"
        print(f"Resetting admin password...")
        print(f"Username: {admin.username}")
        print(f"Email: {admin.email}")
        
        # Hash password
        hashed_password = SecurityUtils.get_password_hash(new_password)
        admin.password_hash = hashed_password
        
        # Save
        db.commit()
        print(f"\n✅ Admin password reset successfully!")
        print(f"New password: {new_password}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin_password()
