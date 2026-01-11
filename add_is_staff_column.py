#!/usr/bin/env python3
"""Check and add is_staff column to users table"""

from database import engine
from sqlalchemy import text

def check_columns():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
        columns = [r[0] for r in result]
        print(f"Current columns: {columns}")
        
        if 'is_staff' not in columns:
            print("Adding is_staff column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_staff BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Column is_staff added successfully")
        else:
            print("Column is_staff already exists")

if __name__ == "__main__":
    check_columns()
