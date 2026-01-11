# 7TY.VN - Docker & PostgreSQL Setup

## System Overview

This is a FastAPI-based agent management system with:
- **Backend**: FastAPI 0.109.0
- **Database**: PostgreSQL 15 (with SQLite fallback)
- **Admin Interface**: pgAdmin 4
- **Containerization**: Docker & Docker Compose

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Network                      │
├──────────────────────┬──────────────────────────────┤
│                      │                               │
│  7TY Application     │  PostgreSQL Database         │
│  (FastAPI)          │  (Port 5432)                 │
│  Port 8000          │                               │
│                      │  ┌──────────────────────┐    │
│                      │  │  pgAdmin 4           │    │
│                      │  │  (Port 5050)         │    │
│                      │  │  Web Browser Access  │    │
│                      │  └──────────────────────┘    │
└──────────────────────┴──────────────────────────────┘
```

## Quick Start

### 1. Prerequisites
- Docker Desktop (Windows/Mac) or Docker + Docker Compose (Linux)
- Git
- 4GB RAM minimum
- 5GB disk space

### 2. Clone and Navigate
```bash
cd c:\Users\LaptopHL\DU_AN\7ty_system
```

### 3. Start Services
```bash
docker-compose up -d
```

Wait 30-60 seconds for PostgreSQL to initialize.

### 4. Verify Services
```bash
docker ps
# Should see: postgres, pgadmin running
```

### 5. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| pgAdmin 4 | http://localhost:5050 | admin@7ty.vn / admin@7ty |
| Application | http://localhost:8000 | (run separately) |
| PostgreSQL | localhost:5432 | 7ty_admin / 7ty_password_secure |

### 6. Run Application

**Option A: Local Python (Development)**
```bash
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Option B: Docker Container**
```bash
docker build -t 7ty-app .
docker run -d \
  --name 7ty-app \
  --env-file .env \
  -p 8000:8000 \
  --network 7ty_network \
  7ty-app
```

## Database Management with pgAdmin

### Access pgAdmin
1. Open browser: http://localhost:5050
2. Email: `admin@7ty.vn`
3. Password: `admin@7ty`

### Add PostgreSQL Server
1. Right-click Servers → Create → Server
2. **General** tab:
   - Name: `7TY_VN`
3. **Connection** tab:
   - Host: `postgres`
   - Port: `5432`
   - Database: `7ty_vn_db`
   - Username: `7ty_admin`
   - Password: `7ty_password_secure`
4. Click Save

### Common Operations
- View tables: Servers → postgres → Databases → 7ty_vn_db → Schemas → public → Tables
- Run queries: Tools → Query Tool
- Backup database: Right-click db → Backup
- Restore database: Right-click db → Restore

## Environment Configuration

### Development (`.env`)
```env
DATABASE_TYPE=postgres
DB_HOST=postgres
DB_PORT=5432
DB_USER=7ty_admin
DB_PASSWORD=7ty_password_secure
DB_NAME=7ty_vn_db
DEBUG=True
```

### Production
```env
DATABASE_TYPE=postgres
DB_HOST=prod-postgres.example.com
DB_PORT=5432
DB_USER=prod_user
DB_PASSWORD=STRONG_PASSWORD_HERE
DB_NAME=7ty_vn_prod
SECRET_KEY=GENERATE_NEW_SECRET_KEY
DEBUG=False
```

## Common Commands

### Docker Operations
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker logs 7ty_postgres
docker logs 7ty_pgadmin

# Restart services
docker-compose restart

# Remove all (including volumes)
docker-compose down -v

# View containers
docker ps

# Execute command in container
docker exec 7ty_postgres psql -U 7ty_admin -d 7ty_vn_db
```

### Database Backup/Restore
```bash
# Backup to file
docker exec 7ty_postgres pg_dump -U 7ty_admin 7ty_vn_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from file
cat backup.sql | docker exec -i 7ty_postgres psql -U 7ty_admin 7ty_vn_db

# Backup with compression
docker exec 7ty_postgres pg_dump -U 7ty_admin -F c 7ty_vn_db > backup.dump
```

### Application Commands
```bash
# Run migrations
python -m alembic upgrade head

# Create admin user
python -c "from quick_start import create_admin; create_admin()"

# Check API health
curl http://localhost:8000/api/health

# View API documentation
# Swagger: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

## Troubleshooting

### PostgreSQL Won't Start
```bash
# Check logs
docker logs 7ty_postgres

# Check if port 5432 is in use
netstat -an | findstr 5432  # Windows
lsof -i :5432              # Mac/Linux

# Reset database
docker-compose down -v
docker-compose up -d
```

### pgAdmin Can't Connect to Database
1. Verify PostgreSQL is running: `docker ps`
2. Check container network: `docker network inspect 7ty_network`
3. Test connection: `docker exec 7ty_postgres psql -U 7ty_admin -d 7ty_vn_db -c "SELECT 1"`

### Application Can't Connect to Database
1. Verify `.env` file has correct settings
2. Check `DB_HOST` - should be `postgres` (container name) or `localhost` (if running locally)
3. Verify network connectivity: `docker network inspect 7ty_network`

### Disk Space Issues
```bash
# Clean up unused Docker resources
docker system prune -a

# Remove volumes separately
docker volume prune
```

## Performance Tuning

### PostgreSQL Configuration (docker-compose.yml)
```yaml
environment:
  POSTGRES_INIT_ARGS: "-c shared_buffers=256MB -c max_connections=200"
```

### Connection Pooling (database.py)
- Configured for 20 pool size + 30 overflow
- Connections recycle every 3600 seconds
- Adjust in `database.py` if needed

## Monitoring

### PostgreSQL Stats
```bash
docker exec 7ty_postgres psql -U 7ty_admin -d 7ty_vn_db -c \
  "SELECT datname, usename, count(*) FROM pg_stat_activity GROUP BY datname, usename;"
```

### Application Logs
```bash
# Real-time logs
docker logs -f 7ty-app

# With timestamps
docker logs --timestamps 7ty-app

# Last 100 lines
docker logs --tail 100 7ty-app
```

## Switching Between SQLite and PostgreSQL

### Use PostgreSQL (Default)
```env
DATABASE_TYPE=postgres
DB_HOST=postgres
```

### Use SQLite
```env
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=./7ty_vn.db
```

Just update `.env` and restart the application.

## Security Notes

⚠️ **Development Defaults - Change Before Production:**
- PostgreSQL password: `7ty_password_secure`
- pgAdmin password: `admin@7ty`
- Application secret key: `your-secret-key-change-in-production`

**Production Checklist:**
- [ ] Generate strong passwords for all services
- [ ] Update SECRET_KEY in .env
- [ ] Enable SSL/TLS for PostgreSQL
- [ ] Use secrets management (AWS Secrets Manager, etc.)
- [ ] Setup firewall rules
- [ ] Enable database encryption
- [ ] Setup automated backups
- [ ] Configure monitoring/alerting
- [ ] Use environment-specific Docker images

## File Structure
```
7ty_system/
├── docker-compose.yml          # Docker Compose configuration
├── Dockerfile                  # Application container image
├── .env                        # Environment variables (development)
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── .dockerignore                # Docker ignore rules
├── config.py                   # Configuration (now PostgreSQL compatible)
├── database.py                 # Database setup (now PostgreSQL compatible)
├── main.py                     # FastAPI application
├── models.py                   # SQLAlchemy models
├── MIGRATION_GUIDE.md          # Detailed migration guide
├── README.md                   # This file
├── routers/                    # API endpoints
│   ├── agents.py
│   ├── auth.py
│   ├── bills.py
│   └── ...
├── static/                     # Frontend files
│   ├── app.html
│   ├── login.html
│   └── uploads/
└── services/                   # Business logic
    ├── email_service.py
    ├── file_service.py
    └── webhook_service.py
```

## Next Steps

1. **Development**: Run locally with Docker database
2. **Testing**: Use pgAdmin to verify data
3. **Backup**: Schedule automated backups
4. **Deploy**: Use this Docker setup for cloud deployment
5. **Scale**: Add multiple app instances with load balancing

## Support

For issues or questions:
1. Check logs: `docker logs [container_name]`
2. Review MIGRATION_GUIDE.md
3. Verify .env configuration
4. Check Docker network: `docker network inspect 7ty_network`

## Version Info
- FastAPI: 0.109.0
- PostgreSQL: 15-alpine
- pgAdmin: Latest
- Python: 3.13
