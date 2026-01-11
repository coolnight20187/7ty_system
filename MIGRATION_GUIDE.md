# Migration Guide: SQLite → PostgreSQL with Docker

## Prerequisites
- Docker Desktop installed
- Docker Compose installed

## Quick Start with Docker

### 1. Start Services
```bash
docker-compose up -d
```

This will start:
- **PostgreSQL**: `localhost:5432`
- **pgAdmin 4**: `http://localhost:5050`
- **Application**: `http://localhost:8000` (when running separately)

### 2. Access pgAdmin 4
1. Go to http://localhost:5050
2. Login with:
   - Email: `admin@7ty.vn`
   - Password: `admin@7ty`

### 3. Connect to PostgreSQL in pgAdmin
1. Right-click "Servers" → Create → Server
2. **General** tab:
   - Name: `7TY_VN`
3. **Connection** tab:
   - Host name/address: `postgres`
   - Port: `5432`
   - Maintenance database: `7ty_vn_db`
   - Username: `7ty_admin`
   - Password: `7ty_password_secure`
4. Click Save

## Running the Application

### Option A: With Docker (Recommended)
```bash
docker-compose up -d
cd 7ty_system
docker build -t 7ty-app .
docker run -d \
  --name 7ty-app \
  --env-file .env \
  -p 8000:8000 \
  --network 7ty_network \
  7ty-app
```

### Option B: Locally (with Docker database)
```bash
# Make sure docker-compose is running
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Run application
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## Environment Variables

Create `.env` file (or copy from `.env.example`):

```env
DATABASE_TYPE=postgres
DB_HOST=postgres          # or localhost if running locally
DB_PORT=5432
DB_USER=7ty_admin
DB_PASSWORD=7ty_password_secure
DB_NAME=7ty_vn_db
SECRET_KEY=your-secret-key
```

## Database Operations

### Initialize Database (First Run)
The application automatically creates tables on startup if they don't exist.

### View Logs
```bash
docker logs 7ty_postgres
docker logs 7ty_pgadmin
```

### Stop Services
```bash
docker-compose down
```

### Remove Everything (Reset)
```bash
docker-compose down -v
# This removes volumes (data will be deleted)
```

## Backup & Restore

### Backup Database
```bash
docker exec 7ty_postgres pg_dump -U 7ty_admin 7ty_vn_db > backup.sql
```

### Restore Database
```bash
cat backup.sql | docker exec -i 7ty_postgres psql -U 7ty_admin 7ty_vn_db
```

## Migration from SQLite

### Option 1: Using Alembic (Recommended for Production)
```bash
pip install alembic
alembic init migrations
# Edit migrations/env.py to use your models
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### Option 2: Manual Data Export/Import

```bash
# 1. Export data from SQLite
sqlite3 7ty_vn.db ".dump" > sqlite_backup.sql

# 2. Start PostgreSQL
docker-compose up -d

# 3. Import to PostgreSQL
# Note: Direct import won't work due to SQL syntax differences
# Use Python script instead:

python migrate_data.py
```

### Create Python Migration Script (migrate_data.py)
```python
import sqlite3
import psycopg2
from models import *

# Connect to SQLite
sqlite_conn = sqlite3.connect('7ty_vn.db')
sqlite_cursor = sqlite_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='7ty_vn_db',
    user='7ty_admin',
    password='7ty_password_secure'
)
pg_cursor = pg_conn.cursor()

# Export tables and insert to PostgreSQL
# (Create migration logic based on your models)

sqlite_conn.close()
pg_conn.close()
```

## Verification

### Check PostgreSQL Connection
```bash
docker exec 7ty_postgres psql -U 7ty_admin -d 7ty_vn_db -c "\dt"
```

### Check Application Health
```bash
curl http://localhost:8000/api/health
```

## Troubleshooting

### Connection Refused
```bash
# Check if containers are running
docker ps

# Check logs
docker logs 7ty_postgres
docker logs 7ty_pgadmin
```

### Permission Denied
```bash
# Restart containers with clean volumes
docker-compose down -v
docker-compose up -d
```

### Slow Startup
PostgreSQL may take 10-15 seconds to initialize. Check health:
```bash
docker logs 7ty_postgres | grep "database system is ready to accept connections"
```

## Production Considerations

1. **Change Default Passwords** in docker-compose.yml and .env
2. **Use Secrets** instead of environment variables for sensitive data
3. **Enable SSL/TLS** for PostgreSQL connections
4. **Setup Regular Backups**:
   ```bash
   # Add to crontab
   0 2 * * * docker exec 7ty_postgres pg_dump -U 7ty_admin 7ty_vn_db > /backups/7ty_$(date +\%Y\%m\%d).sql
   ```
5. **Monitor** with pgAdmin or dedicated monitoring tools
6. **Scale** with multiple app instances using load balancing

## Switching Back to SQLite

If you need to switch back:

1. Update `.env`:
   ```env
   DATABASE_TYPE=sqlite
   SQLITE_DB_PATH=./7ty_vn.db
   ```

2. Stop PostgreSQL:
   ```bash
   docker-compose down
   ```

3. Run the app locally or with SQLite in Docker

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgAdmin Documentation](https://www.pgadmin.org/docs/)
- [SQLAlchemy PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Docker Compose](https://docs.docker.com/compose/)
