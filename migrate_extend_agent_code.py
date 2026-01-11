"""
Migration script to extend agent_code column length
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
    """Extend agent_code column length from 20 to 50"""
    with engine.connect() as connection:
        try:
            print("Extending agent_code column length...")
            
            # Modify column type
            connection.execute(text(
                "ALTER TABLE agents ALTER COLUMN agent_code TYPE VARCHAR(50)"
            ))
            print("✓ Extended agent_code to VARCHAR(50)")
            
            connection.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate()
