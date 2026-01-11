"""
Migration script to add address fields to agents table
"""
import os
from sqlalchemy import text, create_engine

# Configure database connection
DB_HOST = os.getenv("DB_HOST", "7ty_postgres")  # Use container name in Docker
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "7ty_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "7ty_password_secure")
DB_NAME = os.getenv("DB_NAME", "7ty_vn_db")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def migrate():
    """Add address fields to agents table"""
    with engine.connect() as connection:
        try:
            # Check if columns already exist
            result = connection.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='agents' AND column_name='address'"
            ))
            if result.fetchone():
                print("Column 'address' already exists in 'agents' table")
                return
            
            # Add columns
            print("Adding address, city, district, ward columns to agents table...")
            
            connection.execute(text(
                "ALTER TABLE agents ADD COLUMN address VARCHAR(500) NULL"
            ))
            print("✓ Added 'address' column")
            
            connection.execute(text(
                "ALTER TABLE agents ADD COLUMN city VARCHAR(100) NULL"
            ))
            print("✓ Added 'city' column")
            
            connection.execute(text(
                "ALTER TABLE agents ADD COLUMN district VARCHAR(100) NULL"
            ))
            print("✓ Added 'district' column")
            
            connection.execute(text(
                "ALTER TABLE agents ADD COLUMN ward VARCHAR(100) NULL"
            ))
            print("✓ Added 'ward' column")
            
            connection.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate()
