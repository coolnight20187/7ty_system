#!/usr/bin/env python3
"""Create admin user directly using SQLite"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime

# Force SQLite
os.environ['DATABASE_TYPE'] = 'sqlite'

# Import models and security
from models import Base, User, UserRole
from security import get_password_hash

# Create SQLite database
DB_PATH = "./7ty_vn.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"Creating admin user in SQLite database: {DB_PATH}")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Create tables
Base.metadata.create_all(bind=engine)

# Create session
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Check if admin exists
    admin = db.query(User).filter(User.username == "admin").first()
    
    if admin:
        print(f"✓ Admin user already exists!")
        print(f"  Username: admin")
        print(f"  Email: {admin.email}")
        print(f"  Role: {admin.role}")
    else:
        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@7ty.vn",
            password_hash=get_password_hash("Admin@123"),
            phone="+84900000000",
            full_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            created_at=datetime.now()
        )
        db.add(admin_user)
        db.commit()
        print(f"✓ Admin user created successfully!")
        print(f"  Username: admin")
        print(f"  Password: Admin@123")
        print(f"  Email: admin@7ty.vn")
        print(f"  Role: {admin_user.role}")
        
except Exception as e:
    print(f"✗ Error creating admin user: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()

print("\n✓ Database initialization complete!")
print("✓ You can now login with:")
print("  Username: admin")
print("  Password: Admin@123")
