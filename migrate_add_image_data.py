"""
Migration script to add Base64 image data columns to agents table.
This allows storing images directly in database for persistence on cloud platforms.

Run: python migrate_add_image_data.py
"""

import os
import sys

# Set database type
os.environ.setdefault('DATABASE_TYPE', 'sqlite')

from sqlalchemy import text
from database import engine

def migrate():
    """Add image data columns to agents table"""
    
    # New columns to add
    new_columns = [
        ("cccd_front_data", "TEXT"),
        ("cccd_back_data", "TEXT"),
        ("store_image_1_data", "TEXT"),
        ("store_image_2_data", "TEXT"),
        ("store_image_3_data", "TEXT"),
    ]
    
    with engine.connect() as conn:
        # Check database type
        db_url = str(engine.url)
        is_postgres = 'postgresql' in db_url or 'postgres' in db_url
        
        print(f"Database: {'PostgreSQL' if is_postgres else 'SQLite'}")
        print(f"URL: {db_url[:50]}...")
        print()
        
        for col_name, col_type in new_columns:
            try:
                if is_postgres:
                    # PostgreSQL syntax
                    sql = text(f"ALTER TABLE agents ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                else:
                    # SQLite syntax - check if column exists first
                    result = conn.execute(text("PRAGMA table_info(agents)"))
                    columns = [row[1] for row in result.fetchall()]
                    
                    if col_name in columns:
                        print(f"✓ Column '{col_name}' already exists")
                        continue
                    
                    sql = text(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type}")
                
                conn.execute(sql)
                conn.commit()
                print(f"✓ Added column '{col_name}'")
                
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"✓ Column '{col_name}' already exists")
                else:
                    print(f"✗ Error adding column '{col_name}': {e}")
        
        print()
        print("=" * 50)
        print("Migration completed!")
        print()
        print("Image data columns added to 'agents' table:")
        print("  - cccd_front_data: CCCD mặt trước (Base64)")
        print("  - cccd_back_data: CCCD mặt sau (Base64)")
        print("  - store_image_1_data: Ảnh cửa hàng 1 (Base64)")
        print("  - store_image_2_data: Ảnh cửa hàng 2 (Base64)")
        print("  - store_image_3_data: Ảnh cửa hàng 3 (Base64)")
        print()
        print("Images will now be stored in database instead of filesystem.")
        print("This ensures data persistence on cloud platforms like Render.")


if __name__ == "__main__":
    migrate()
