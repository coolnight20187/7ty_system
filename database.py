from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON, Enum, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import QueuePool, NullPool
from contextlib import contextmanager
import enum
from datetime import datetime
from typing import Generator, Optional
import logging

from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Determine connection pool based on database type
pool_class = NullPool if settings.DATABASE_URL.startswith("sqlite") else QueuePool

# Create engine with connection pooling
engine_kwargs = {
    "echo": False,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "poolclass": NullPool,
        "connect_args": {"check_same_thread": False}
    })
else:
    # PostgreSQL settings
    engine_kwargs.update({
        "poolclass": QueuePool,
        "pool_size": 20,
        "max_overflow": 30,
        "pool_pre_ping": True,
        "pool_recycle": 3600,  # Recycle connections every hour
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Dependency to get DB session
def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session
    Yields a SQLAlchemy session and closes it after use
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions
    Use for non-FastAPI contexts
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()

def init_db():
    """
    Initialize database tables
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def drop_db():
    """
    Drop all database tables (for testing only)
    """
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise

# Database helper functions
def paginate_query(query, page: int = 1, limit: int = 10):
    """
    Helper function to paginate SQLAlchemy queries
    """
    offset = (page - 1) * limit
    return query.offset(offset).limit(limit)

def get_or_create(db: Session, model, **kwargs):
    """
    Get an instance or create if it doesn't exist
    """
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        instance = model(**kwargs)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance, True

# Database health check
def check_database_health() -> dict:
    """
    Check database connection health
    Returns health status and connection info
    """
    try:
        with engine.connect() as conn:
            # Try a simple query
            conn.execute("SELECT 1")
            
        return {
            "status": "healthy",
            "database": engine.url.database,
            "driver": engine.url.drivername,
            "pool_size": engine.pool.size(),
            "pool_checked_in": engine.pool.checkedin(),
            "pool_checked_out": engine.pool.checkedout(),
            "pool_overflow": engine.pool.overflow()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": engine.url.database if hasattr(engine, 'url') else "unknown"
        }

# Connection pool monitoring
def get_connection_pool_stats() -> dict:
    """
    Get connection pool statistics
    """
    try:
        return {
            "size": engine.pool.size(),
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
            "connections": engine.pool.status()
        }
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        return {"error": str(e)}

# Database maintenance functions
def vacuum_database():
    """
    Perform database maintenance (SQLite specific)
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuum completed")
                return {"status": "success", "message": "Database vacuum completed"}
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return {"status": "error", "error": str(e)}
    return {"status": "skipped", "message": "VACUUM only supported for SQLite"}

def optimize_database():
    """
    Optimize database performance
    """
    try:
        # SQLite specific optimizations
        if settings.DATABASE_URL.startswith("sqlite"):
            with engine.connect() as conn:
                conn.execute("PRAGMA optimize")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("Database optimization completed")
                return {"status": "success", "message": "Database optimized"}
        
        # PostgreSQL specific optimizations
        elif settings.DATABASE_URL.startswith("postgresql"):
            with engine.connect() as conn:
                conn.execute("VACUUM ANALYZE")
                logger.info("Database VACUUM ANALYZE completed")
                return {"status": "success", "message": "Database VACUUM ANALYZE completed"}
        
        return {"status": "skipped", "message": "No optimization for current database"}
    
    except Exception as e:
        logger.error(f"Failed to optimize database: {e}")
        return {"status": "error", "error": str(e)}

# Backup and restore functions (simplified)
def create_backup(backup_path: str = None) -> dict:
    """
    Create database backup
    """
    from shutil import copyfile
    import os
    
    try:
        if settings.DATABASE_URL.startswith("sqlite"):
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            if not os.path.exists(db_path):
                return {"status": "error", "error": "Database file not found"}
            
            if backup_path is None:
                backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            copyfile(db_path, backup_path)
            logger.info(f"Database backup created: {backup_path}")
            return {
                "status": "success",
                "message": "Backup created",
                "backup_path": backup_path,
                "size": os.path.getsize(backup_path)
            }
        
        return {"status": "skipped", "message": "Backup only supported for SQLite"}
    
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return {"status": "error", "error": str(e)}

# Migration utilities
def get_table_info(table_name: str) -> dict:
    """
    Get information about a table
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(f"PRAGMA table_info({table_name})") \
                if settings.DATABASE_URL.startswith("sqlite") \
                else conn.execute(f"""
                    SELECT column_name, data_type, is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                """)
            
            columns = []
            for row in result:
                columns.append(dict(row))
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns)
            }
    except Exception as e:
        logger.error(f"Failed to get table info: {e}")
        return {"error": str(e)}

def get_all_tables() -> list:
    """
    Get list of all tables in database
    """
    try:
        with engine.connect() as conn:
            if settings.DATABASE_URL.startswith("sqlite"):
                result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            elif settings.DATABASE_URL.startswith("postgresql"):
                result = conn.execute("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
            else:
                return []
            
            return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get tables: {e}")
        return []

# Transaction management
@contextmanager
def transaction(db: Session):
    """
    Context manager for manual transaction control
    """
    try:
        yield
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction failed: {e}")
        raise

# Bulk operations helper
def bulk_insert(db: Session, model, data_list: list):
    """
    Perform bulk insert with error handling
    """
    try:
        db.bulk_insert_mappings(model, data_list)
        db.commit()
        logger.info(f"Bulk insert completed: {len(data_list)} records")
        return {"status": "success", "count": len(data_list)}
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk insert failed: {e}")
        return {"status": "error", "error": str(e)}

def bulk_update(db: Session, model, data_list: list, update_fields: list):
    """
    Perform bulk update with error handling
    """
    try:
        db.bulk_update_mappings(model, data_list)
        db.commit()
        logger.info(f"Bulk update completed: {len(data_list)} records")
        return {"status": "success", "count": len(data_list)}
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk update failed: {e}")
        return {"status": "error", "error": str(e)}