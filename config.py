import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "7TY.VN"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    ALLOWED_HOSTS: list = ["*"]
    
    # Database - Support both SQLite and PostgreSQL
    DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "sqlite")  # "sqlite" or "postgres"
    
    # PostgreSQL settings (used if DATABASE_TYPE="postgres")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 5432))
    DB_USER: str = os.getenv("DB_USER", "7ty_admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "7ty_password_secure")
    DB_NAME: str = os.getenv("DB_NAME", "7ty_vn_db")
    
    # SQLite settings (used if DATABASE_TYPE="sqlite")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./7ty_vn.db")
    
    @property
    def DATABASE_URL(self) -> str:
        """Generate database URL based on type"""
        if self.DATABASE_TYPE.lower() == "postgres":
            # Use the DB_HOST from environment (supports both localhost and Docker container names)
            return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            return f"sqlite:///{self.SQLITE_DB_PATH}"
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
    RESET_TOKEN_EXPIRE_HOURS: int = int(os.getenv("RESET_TOKEN_EXPIRE_HOURS", 24))
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    # Security
    PASSWORD_HASH_ALGORITHM: str = "bcrypt"
    SESSION_EXPIRE_MINUTES: int = 60
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    
    # File upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER: str = "./static/uploads"
    ALLOWED_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".pdf", ".csv", ".xlsx"]
    
    # Email (optional)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    
    # API Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Webhook
    WEBHOOK_SECRET: Optional[str] = None
    
    # Bill Lookup API (DailyShopee)
    BILL_API_BASE_URL: str = os.getenv("BILL_API_BASE_URL", "https://api.dailyshopee.vn")
    BILL_API_PATH: str = os.getenv("BILL_API_PATH", "/airpay/v1/apc.order.AppService/GetBill")
    BILL_API_COOKIE: str = os.getenv("BILL_API_COOKIE", "_ga=GA1.1.2001015767.1752118269; _ga_LMDMPJ94ME=GS2.1.s1757299657$o2$g1$t1757301026$j60$l0$h0; token=528c1b7aabd70a85f148dc04d9690448bebeef3bb1cda3f84e04395fac11701feba5d1fd1328aab2b2fca80f4a1cdb94; uid=300052014")
    BILL_API_CSRF_TOKEN: str = os.getenv("BILL_API_CSRF_TOKEN", "dc37d4fff8aa47188fa9efd733696d6d")
    
    # Proxy Pool Configuration
    # Format: "http://user:pass@host:port" or "http://host:port"
    # Multiple proxies separated by comma
    PROXY_LIST: str = os.getenv("PROXY_LIST", "")
    PROXY_ENABLED: bool = os.getenv("PROXY_ENABLED", "false").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Alias for backward compatibility
Config = Settings