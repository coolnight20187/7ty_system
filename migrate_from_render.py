#!/usr/bin/env python3
"""
Migrate data from Render PostgreSQL to local SQLite database
"""
import os
os.environ['DATABASE_URL'] = 'postgresql://appadmin:uz4Lvrc3qbSsD64bB1PMus7WjE0YeTtI@dpg-d5hrtd24d50c7399kp80-a.oregon-postgres.render.com/appdb_jtab'

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import SessionLocal
from models import User, Agent, Customer, UserRole

# Render PostgreSQL connection
RENDER_URL = 'postgresql://appadmin:uz4Lvrc3qbSsD64bB1PMus7WjE0YeTtI@dpg-d5hrtd24d50c7399kp80-a.oregon-postgres.render.com/appdb_jtab'

def migrate():
    print("🔄 Connecting to Render PostgreSQL...")
    render_engine = create_engine(RENDER_URL)
    RenderSession = sessionmaker(bind=render_engine)
    render_db = RenderSession()
    
    print("🔄 Connecting to local database...")
    local_db = SessionLocal()
    
    try:
        # Migrate Users
        print("\n📥 Migrating Users...")
        users = render_db.execute(text("SELECT * FROM users")).fetchall()
        print(f"   Found {len(users)} users")
        
        for user in users:
            # Check if user already exists
            existing = local_db.query(User).filter(User.username == user.username).first()
            if existing:
                print(f"   ⏭️  User '{user.username}' already exists, skipping...")
                continue
                
            new_user = User(
                username=user.username,
                email=user.email,
                phone=user.phone,
                full_name=user.full_name,
                password_hash=user.password_hash,
                role=UserRole(user.role) if user.role else UserRole.AGENT,
                is_staff=user.is_staff or False,
                is_active=user.is_active or True,
                is_verified=user.is_verified or False,
            )
            local_db.add(new_user)
            print(f"   ✅ Migrated user: {user.username}")
        
        local_db.commit()
        
        # Get user mapping for foreign keys
        user_mapping = {}
        for user in users:
            local_user = local_db.query(User).filter(User.username == user.username).first()
            if local_user:
                user_mapping[user.id] = local_user.id
        
        # Migrate Agents
        print("\n📥 Migrating Agents...")
        agents = render_db.execute(text("SELECT * FROM agents")).fetchall()
        print(f"   Found {len(agents)} agents")
        
        for agent in agents:
            existing = local_db.query(Agent).filter(Agent.agent_code == agent.agent_code).first()
            if existing:
                print(f"   ⏭️  Agent '{agent.agent_code}' already exists, skipping...")
                continue
                
            new_agent = Agent(
                user_id=user_mapping.get(agent.user_id, agent.user_id),
                agent_code=agent.agent_code,
                agent_name=agent.agent_name,
                phone=agent.phone,
                email=agent.email,
                address=agent.address,
                city=agent.city,
                district=agent.district,
                ward=agent.ward,
                agent_type=agent.agent_type,
                status=agent.status,
                balance=agent.balance or 0,
                total_customers=agent.total_customers or 0,
                total_transactions=agent.total_transactions or 0,
                total_deposit=agent.total_deposit or 0,
                total_withdraw=agent.total_withdraw or 0,
                total_commission=agent.total_commission or 0,
            )
            local_db.add(new_agent)
            print(f"   ✅ Migrated agent: {agent.agent_code} - {agent.agent_name}")
        
        local_db.commit()
        
        # Migrate Customers
        print("\n📥 Migrating Customers...")
        customers = render_db.execute(text("SELECT * FROM customers")).fetchall()
        print(f"   Found {len(customers)} customers")
        
        for customer in customers:
            existing = local_db.query(Customer).filter(Customer.customer_code == customer.customer_code).first()
            if existing:
                print(f"   ⏭️  Customer '{customer.customer_code}' already exists, skipping...")
                continue
            
            new_customer = Customer(
                customer_code=customer.customer_code,
                full_name=customer.full_name,
                phone=customer.phone,
                email=customer.email,
                address=customer.address,
                city=customer.city,
                district=customer.district,
                ward=customer.ward,
                user_id=user_mapping.get(customer.user_id, customer.user_id) if customer.user_id else None,
                bank_name=customer.bank_name,
                card_type=customer.card_type,
                card_last_digits=customer.card_last_digits,
                credit_limit=customer.credit_limit or 0,
                customer_type=customer.customer_type,
                is_active=customer.is_active or True,
            )
            local_db.add(new_customer)
            print(f"   ✅ Migrated customer: {customer.customer_code} - {customer.full_name}")
        
        local_db.commit()
        
        print("\n✅ Migration completed successfully!")
        
        # Print summary
        print("\n📊 Summary:")
        print(f"   Users: {local_db.query(User).count()}")
        print(f"   Agents: {local_db.query(Agent).count()}")
        print(f"   Customers: {local_db.query(Customer).count()}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        local_db.rollback()
        raise
    finally:
        render_db.close()
        local_db.close()

if __name__ == "__main__":
    migrate()
