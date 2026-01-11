#!/usr/bin/env python3
"""
Migration: Add agent_name column to agents table
"""

import os
import sys
import logging
from sqlalchemy import create_engine, Column, String, text
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://7ty_admin:7ty_password_secure@7ty_postgres:5432/7ty_vn_db')

def migrate():
    """Add agent_name column to agents table"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Check if column already exists
            result = connection.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='agents' AND column_name='agent_name'
            """))
            
            if result.fetchone():
                logger.info("✅ agent_name column already exists")
                return
            
            # Add agent_name column
            logger.info("Adding agent_name column to agents table...")
            connection.execute(text("""
                ALTER TABLE agents ADD COLUMN agent_name VARCHAR(100) NOT NULL DEFAULT 'Default Agent'
            """))
            connection.commit()
            
            # Update existing agents with a proper agent_name based on user's full_name
            logger.info("Updating existing agents with agent_name...")
            connection.execute(text("""
                UPDATE agents 
                SET agent_name = COALESCE(u.full_name, 'Agent-' || agents.agent_code)
                FROM users u 
                WHERE agents.user_id = u.id AND agents.agent_name = 'Default Agent'
            """))
            connection.commit()
            
            logger.info("✅ Migration completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
