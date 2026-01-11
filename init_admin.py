#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, '/app')

from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import User, UserRole
from security import get_password_hash

# Create tables
Base.metadata.create_all(bind=engine)

# Create session
db: Session = SessionLocal()

try:
    # Check if admin exists
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@7ty.vn",
            password_hash=get_password_hash("Admin@123"),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True
        )
        db.add(admin_user)
        db.commit()
        print("Admin user created successfully!")
        print("Username: admin")
        print("Password: Admin@123")
        print("Email: admin@7ty.vn")
    else:
        print("Admin user already exists!")
finally:
    db.close()
