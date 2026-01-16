#!/usr/bin/env python3
"""
Sync data from Render PostgreSQL to Docker PostgreSQL
"""
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Render PostgreSQL
RENDER_URL = 'postgresql://appadmin:uz4Lvrc3qbSsD64bB1PMus7WjE0YeTtI@dpg-d5hrtd24d50c7399kp80-a.oregon-postgres.render.com/appdb_jtab'

# Docker PostgreSQL  
DOCKER_URL = 'postgresql://7ty_admin:7ty_password_secure@localhost:5432/7ty_vn_db'

def sync_table(render_db, docker_db, table_name, id_column='id'):
    """Sync a table from Render to Docker"""
    print(f"\n📥 Syncing {table_name}...")
    
    # Get data from Render
    try:
        render_data = render_db.execute(text(f"SELECT * FROM {table_name}")).fetchall()
        render_columns = render_db.execute(text(f"SELECT * FROM {table_name} LIMIT 0")).keys()
        columns = list(render_columns)
    except Exception as e:
        print(f"   ❌ Error reading from Render: {e}")
        return 0
    
    print(f"   Found {len(render_data)} records in Render")
    
    if len(render_data) == 0:
        return 0
    
    # Get existing IDs in Docker
    try:
        docker_ids = docker_db.execute(text(f"SELECT {id_column} FROM {table_name}")).fetchall()
        existing_ids = set(row[0] for row in docker_ids)
    except Exception as e:
        print(f"   ⚠️ Table might not exist in Docker: {e}")
        existing_ids = set()
    
    # Insert missing records
    inserted = 0
    for row in render_data:
        row_dict = dict(zip(columns, row))
        if row_dict.get(id_column) in existing_ids:
            continue
        
        # Convert dict/list values to JSON strings for PostgreSQL JSON columns
        for key, value in row_dict.items():
            if isinstance(value, (dict, list)):
                row_dict[key] = json.dumps(value)
        
        try:
            cols = ', '.join(columns)
            placeholders = ', '.join([f':{c}' for c in columns])
            docker_db.execute(
                text(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"),
                row_dict
            )
            inserted += 1
        except Exception as e:
            docker_db.rollback()  # Rollback to continue after error
            err_msg = str(e)
            if "duplicate key" not in err_msg.lower():
                print(f"   ⚠️ Skip row: {err_msg[:80]}")
    
    docker_db.commit()
    print(f"   ✅ Inserted {inserted} new records")
    return inserted

def main():
    print("🔄 Connecting to databases...")
    
    render_engine = create_engine(RENDER_URL)
    docker_engine = create_engine(DOCKER_URL)
    
    RenderSession = sessionmaker(bind=render_engine)
    DockerSession = sessionmaker(bind=docker_engine)
    
    render_db = RenderSession()
    docker_db = DockerSession()
    
    try:
        # Disable foreign key checks for transactions
        docker_db.execute(text("SET session_replication_role = 'replica'"))
        
        # Sync all tables with data
        tables = [
            'users', 'agents', 'customers', 'transactions', 'bills',
            'activity_logs', 'system_bank_accounts', 'system_configs',
            'deposit_requests', 'notifications', 'reward_programs',
            'reward_transactions', 'commission_logs', 'deposit_limits',
            'api_logs', 'deposit_security_logs'
        ]
        
        for table in tables:
            try:
                sync_table(render_db, docker_db, table)
            except Exception as e:
                print(f"   ❌ Error syncing {table}: {e}")
        
        # Re-enable foreign key checks
        docker_db.execute(text("SET session_replication_role = 'origin'"))
        docker_db.commit()
        
        # Print summary
        print("\n📊 Summary (Docker PostgreSQL):")
        for table in tables:
            try:
                count = docker_db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"   {table}: {count}")
            except:
                print(f"   {table}: N/A")
        
    finally:
        render_db.close()
        docker_db.close()

if __name__ == "__main__":
    main()
