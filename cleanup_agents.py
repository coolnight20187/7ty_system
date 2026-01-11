"""
Script to clean up old agents and users
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Configure database connection
DB_HOST = os.getenv("DB_HOST", "7ty_postgres")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "7ty_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "7ty_password_secure")
DB_NAME = os.getenv("DB_NAME", "7ty_vn_db")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Import models
from models import Agent, User

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def cleanup_agents():
    """Clean up old agents and their users (keep only admin)"""
    db = SessionLocal()
    try:
        # Get all agents
        agents = db.query(Agent).all()
        print(f"Found {len(agents)} agents")
        
        # Delete agents and their users
        for agent in agents:
            print(f"Deleting agent: {agent.agent_code} (user: {agent.user.username})")
            
            # Delete agent
            db.delete(agent)
            
            # Delete associated user (except admin)
            if agent.user.username != "admin":
                db.delete(agent.user)
        
        db.commit()
        print(f"\n✅ Cleaned up {len(agents)} agents")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_agents()
