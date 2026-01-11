"""
Migration script to add new columns to users table
"""
from database import engine
from sqlalchemy import text
import sys

def run_migration():
    alter_statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(10)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS cccd_front VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS cccd_back VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notes TEXT"
    ]
    
    try:
        conn = engine.connect()
        for stmt in alter_statements:
            try:
                conn.execute(text(stmt))
                print(f"Executed: {stmt}")
            except Exception as e:
                print(f"Error: {e}")
        conn.commit()
        conn.close()
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
