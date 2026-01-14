import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, WebSocket, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

from config import settings
from database import engine, Base, get_db
from dependencies import get_current_user, get_current_active_user

# Import routers carefully with error handling
auth = None
users = None
agents = None
bills = None
transactions = None
api = None
system = None
customers = None
reports = None
notifications = None

try:
    from routers import auth
except ImportError as e:
    logging.warning(f"Failed to import auth router: {e}")

try:
    from routers import users
except ImportError as e:
    logging.warning(f"Failed to import users router: {e}")

try:
    from routers import agents
except ImportError as e:
    logging.warning(f"Failed to import agents router: {e}")

try:
    from routers import bills
except ImportError as e:
    logging.warning(f"Failed to import bills router: {e}")

try:
    from routers import transactions
except ImportError as e:
    logging.warning(f"Failed to import transactions router: {e}")

try:
    from routers import api as api_router
    api = api_router
except ImportError as e:
    logging.warning(f"Failed to import api router: {e}")

try:
    from routers import system
except ImportError as e:
    logging.warning(f"Failed to import system router: {e}")

try:
    from routers import customers
except ImportError as e:
    logging.warning(f"Failed to import customers router: {e}")

try:
    from routers import reports
except ImportError as e:
    logging.warning(f"Failed to import reports router: {e}")

try:
    from routers import notifications
except ImportError as e:
    logging.warning(f"Failed to import notifications router: {e}")

try:
    from routers import rewards
except ImportError as e:
    logging.warning(f"Failed to import rewards router: {e}")

# Email webhook router
email_webhook = None
try:
    from routers import email_webhook
except ImportError as e:
    logging.warning(f"Failed to import email_webhook router: {e}")

# Deposit security router  
deposit = None
try:
    from routers import deposit
except ImportError as e:
    logging.warning(f"Failed to import deposit router: {e}")

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời ứng dụng"""
    # Startup
    logger.info("Starting 7TY.VN System...")
    
    # Tạo bảng database
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    
    # Chạy migrations cho các cột mới
    await run_migrations()
    
    # Khởi tạo tài khoản Admin chính thức
    await init_admin_account()
    
    yield
    
    # Shutdown
    logger.info("Shutting down 7TY.VN System...")


async def run_migrations():
    """Chạy migrations để thêm các cột mới vào database"""
    from sqlalchemy import text
    
    try:
        with engine.connect() as conn:
            db_url = str(engine.url)
            is_postgres = 'postgresql' in db_url or 'postgres' in db_url
            
            # Danh sách các cột cần thêm vào bảng agents
            new_columns = [
                ("cccd_front_data", "TEXT"),
                ("cccd_back_data", "TEXT"),
                ("store_image_1_data", "TEXT"),
                ("store_image_2_data", "TEXT"),
                ("store_image_3_data", "TEXT"),
            ]
            
            for col_name, col_type in new_columns:
                try:
                    if is_postgres:
                        sql = text(f"ALTER TABLE agents ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                        conn.execute(sql)
                        conn.commit()
                    else:
                        # SQLite - check if column exists
                        result = conn.execute(text("PRAGMA table_info(agents)"))
                        columns = [row[1] for row in result.fetchall()]
                        if col_name not in columns:
                            sql = text(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type}")
                            conn.execute(sql)
                            conn.commit()
                            logger.info(f"Added column: {col_name}")
                except Exception as e:
                    if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                        logger.warning(f"Migration warning for {col_name}: {e}")
            
            logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Migration error: {e}")


async def init_admin_account():
    """
    Khởi tạo tài khoản Admin chính thức khi server khởi động.
    Sử dụng biến môi trường ADMIN_USERNAME và ADMIN_PASSWORD để bảo mật.
    """
    from sqlalchemy.orm import Session
    from models import User, UserRole
    from security import get_password_hash
    from datetime import timezone
    
    # Lấy thông tin từ biến môi trường
    admin_username = os.environ.get('ADMIN_USERNAME', 'phanminhphong')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    admin_email = os.environ.get('ADMIN_EMAIL', f'{admin_username}@7ty.vn')
    admin_fullname = os.environ.get('ADMIN_FULLNAME', 'Phan Minh Phong')
    
    # Chỉ tạo nếu có ADMIN_PASSWORD trong biến môi trường
    if not admin_password:
        logger.info("ADMIN_PASSWORD not set - skipping admin creation. Set environment variable to auto-create admin.")
        return
    
    db: Session = next(get_db())
    try:
        # Kiểm tra admin đã tồn tại chưa
        existing_admin = db.query(User).filter(
            (User.username == admin_username) | (User.role == UserRole.ADMIN)
        ).first()
        
        if existing_admin:
            logger.info(f"Admin account already exists: {existing_admin.username}")
            return
        
        # Tạo tài khoản admin mới
        admin_user = User(
            username=admin_username,
            email=admin_email,
            full_name=admin_fullname,
            password_hash=get_password_hash(admin_password),
            role=UserRole.ADMIN,
            is_active=True,
            is_staff=True,
            is_verified=True,
            is_deleted=False,
            login_attempts=0,
            two_factor_enabled=False,
            api_calls_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(admin_user)
        db.commit()
        
        logger.info(f"✅ Admin account created successfully!")
        logger.info(f"   Username: {admin_username}")
        logger.info(f"   Email: {admin_email}")
        logger.info(f"   Role: ADMIN")
        
    except Exception as e:
        logger.error(f"Error creating admin account: {e}")
        db.rollback()
    finally:
        db.close()
    # Đóng kết nối database, v.v.

async def initialize_sample_data():
    """Khởi tạo dữ liệu mẫu cho hệ thống"""
    from sqlalchemy.orm import Session
    from models import User
    from utils import get_password_hash
    
    db: Session = next(get_db())
    try:
        # Kiểm tra và tạo admin user nếu chưa có
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin_user = User(
                username="admin",
                email="admin@7ty.vn",
                full_name="Administrator",
                password_hash=get_password_hash("Admin@123"),
                role="admin",
                is_active=True,
                phone="0987654321",
                created_at=datetime.utcnow()
            )
            db.add(admin_user)
            db.commit()
            logger.info("Admin user created successfully")
        
        logger.info("Sample data initialized")
    except Exception as e:
        logger.error(f"Error initializing sample data: {e}")
    finally:
        db.close()

# Khởi tạo FastAPI app
app = FastAPI(
    title="7TY.VN - Hệ Thống Quản Trị Đại Lý Thu Hộ",
    description="Hệ thống quản lý đại lý thu hộ điện với API tích hợp đầy đủ",
    version="4.0.0",
    contact={
        "name": "7TY.VN Support",
        "email": "support@7ty.vn"
    },
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Xử lý HTTP exceptions"""
    logger.warning(f"HTTPException: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Xử lý general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "Please contact administrator"
        }
    )

# Mount static files
os.makedirs("static/uploads", exist_ok=True)

# Note: Root route "/" is defined below after static mount

# Login page
@app.get("/login")
@app.get("/login.html")
async def login_page():
    """Serve login page"""
    try:
        return FileResponse("static/login.html", media_type="text/html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Login page not found")

# Agent mobile app route
@app.get("/agent_app.html")
async def agent_app():
    """Serve agent mobile app"""
    try:
        return FileResponse("static/agent_app.html", media_type="text/html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Agent app not found")

# APK download route - serve with correct headers to prevent zip compression
@app.get("/download/apk")
@app.get("/download/agent-apk")
@app.get("/static/uploads/7ty-agent-latest.apk")
async def download_apk():
    """Download Agent APK file with correct headers"""
    # Ưu tiên file mới nhất trong static/apk
    new_apk_path = "static/apk/agent-app-v2.132.0.apk"
    old_apk_path = "static/uploads/7ty-agent-latest.apk"
    
    apk_path = new_apk_path if os.path.exists(new_apk_path) else old_apk_path
    
    if not os.path.exists(apk_path):
        raise HTTPException(status_code=404, detail="APK file not found")
    
    return FileResponse(
        path=apk_path,
        media_type="application/vnd.android.package-archive",
        filename="agent-app-v2.132.0.apk",
        headers={
            "Content-Disposition": "attachment; filename=agent-app-v2.132.0.apk",
            "Content-Type": "application/vnd.android.package-archive",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff"
        }
    )

@app.get("/download/sms-reader-apk")
async def download_sms_reader_apk():
    """Download SMS Reader APK file"""
    apk_path = "static/apk/sms-reader-v2.132.0.apk"
    
    if not os.path.exists(apk_path):
        raise HTTPException(status_code=404, detail="SMS Reader APK not found")
    
    return FileResponse(
        path=apk_path,
        media_type="application/vnd.android.package-archive",
        filename="sms-reader-v2.132.0.apk",
        headers={
            "Content-Disposition": "attachment; filename=sms-reader-v2.132.0.apk",
            "Content-Type": "application/vnd.android.package-archive",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff"
        }
    )

app.mount("/static", StaticFiles(directory="static"), name="static")

# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "7ty_system"
    }

@app.get("/api/status")
async def api_status(current_user = Depends(get_current_active_user)):
    """Kiểm tra trạng thái API"""
    return {
        "success": True,
        "status": "online",
        "user": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    }

# Include routers (with safety checks)
if auth:
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
if users:
    app.include_router(users.router, prefix="/api/users", tags=["Users"])
if agents:
    app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
if bills:
    app.include_router(bills.router, prefix="/api/bills", tags=["Bills"])
if transactions:
    app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
if customers:
    app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
if reports:
    app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
if notifications:
    app.include_router(notifications.router, tags=["Notifications"])
if api:
    app.include_router(api.router, prefix="/api/v1", tags=["External API"])
if system:
    app.include_router(system.router, prefix="/api/system", tags=["System"])
if rewards:
    app.include_router(rewards.router, prefix="/api/rewards", tags=["Rewards"])
if email_webhook:
    app.include_router(email_webhook.router, prefix="/api/v1", tags=["Email Webhook"])
if deposit:
    app.include_router(deposit.router, prefix="/api/v1", tags=["Deposit"])

# WebSocket endpoints
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint cho real-time updates"""
    from routers.websocket import websocket_endpoint as ws_router_endpoint
    
    # Gọi endpoint từ router
    try:
        await ws_router_endpoint(websocket, token=token)
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        try:
            await websocket.close(code=1000)
        except:
            pass

# Phục vụ login page
@app.get("/login")
async def serve_login():
    """Phục vụ trang đăng nhập"""
    from fastapi.responses import FileResponse
    return FileResponse("static/login.html")

# Explicit frontend routes (to avoid catch-all interfering with API routes)
@app.get("/")
async def serve_root():
    """Serve frontend at root"""
    from fastapi.responses import FileResponse
    if os.path.exists("static/app.html"):
        return FileResponse("static/app.html")
    raise HTTPException(status_code=404, detail="Application not found")

@app.get("/dashboard")
async def serve_dashboard():
    """Serve frontend for dashboard route"""
    from fastapi.responses import FileResponse
    if os.path.exists("static/app.html"):
        return FileResponse("static/app.html")
    raise HTTPException(status_code=404, detail="Application not found")

@app.get("/agents")
async def serve_agents():
    """Serve frontend for agents route"""
    from fastapi.responses import FileResponse
    if os.path.exists("static/app.html"):
        return FileResponse("static/app.html")
    raise HTTPException(status_code=404, detail="Application not found")

@app.get("/customers")
async def serve_customers():
    """Serve frontend for customers route"""
    from fastapi.responses import FileResponse
    if os.path.exists("static/app.html"):
        return FileResponse("static/app.html")
    raise HTTPException(status_code=404, detail="Application not found")

@app.get("/reports")
async def serve_reports():
    """Serve frontend for reports route"""
    from fastapi.responses import FileResponse
    if os.path.exists("static/app.html"):
        return FileResponse("static/app.html")
    raise HTTPException(status_code=404, detail="Application not found")

# Run application
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level="info" if settings.DEBUG else "warning",
        access_log=True
    )
