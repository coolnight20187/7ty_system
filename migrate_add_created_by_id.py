"""
Migration script to add created_by_id field to agents table
"""
import os
from sqlalchemy import text, create_engine

# Configure database connection
DB_HOST = os.getenv("DB_HOST", "7ty_postgres")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "7ty_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "7ty_password_secure")
DB_NAME = os.getenv("DB_NAME", "7ty_vn_db")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def migrate():
    """Add created_by_id field to agents table"""
    with engine.connect() as connection:
        try:
            # Check if column already exists
            result = connection.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='agents' AND column_name='created_by_id'"
            ))
            if result.fetchone():
                print("Column 'created_by_id' already exists in 'agents' table")
                return
            
            print("Adding created_by_id column to agents table...")
            
            # Add foreign key constraint
            connection.execute(text(
                "ALTER TABLE agents ADD COLUMN created_by_id INTEGER NULL"
            ))
            print("✓ Added 'created_by_id' column")
            
            # Add foreign key constraint
            connection.execute(text(
                "ALTER TABLE agents ADD CONSTRAINT fk_agents_created_by_id FOREIGN KEY (created_by_id) REFERENCES users(id)"
            ))
            print("✓ Added foreign key constraint")
            
            connection.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate()
