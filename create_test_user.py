"""
Script to create a test user account
"""
from database import engine, get_db
from models import User, UserRole
from sqlalchemy import text
from datetime import datetime

def create_test_user():
    db = next(get_db())
    try:
        # Check if test user exists
        existing = db.query(User).filter(User.username == "0901234567").first()
        if existing:
            print(f"Test user already exists: ID={existing.id}")
            return
        
        # Create test user
        user = User(
            username="0901234567",
            phone="0901234567",
            email="test@7ty.vn",
            full_name="Nguyen Van Test",
            role=UserRole.STAFF,
            is_active=True,
            identity_card="123456789012",
            address="123 Test Street, District 1, Ho Chi Minh City",
            gender="male"
        )
        user.set_password("Test@123456")
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"Test user created successfully!")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Full Name: {user.full_name}")
        print(f"  Phone: {user.phone}")
        print(f"  Role: {user.role.value}")
        print(f"  Password: Test@123456")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
