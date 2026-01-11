import os
import json
import logging
import hashlib
import random
import string
import secrets
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union, Tuple, TYPE_CHECKING
from decimal import Decimal, ROUND_HALF_UP
import re
import asyncio
from pathlib import Path
import mimetypes
import smtplib

# Type checking imports (avoid circular import)
if TYPE_CHECKING:
    from models import User, Agent, Bill, Transaction, Customer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import qrcode
import base64
from io import BytesIO
import csv
import xlsxwriter
from fastapi import UploadFile
import aiofiles
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import pandas as pd
from openpyxl import Workbook
import openpyxl
import uuid

from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Security utilities
class SecurityUtils:
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    PASSWORD_MAX_BYTES = 72  # bcrypt limitation
    
    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        # Truncate password to max bytes to match hashing behavior
        truncated_password = cls._truncate_password(plain_password)
        return cls._pwd_context.verify(truncated_password, hashed_password)
    
    @classmethod
    def get_password_hash(cls, password: str) -> str:
        """Generate password hash - automatically truncates to 72 bytes due to bcrypt limitation"""
        try:
            truncated_password = cls._truncate_password(password)
            return cls._pwd_context.hash(truncated_password)
        except ValueError as e:
            # If bcrypt still complains, force truncate
            if "72" in str(e) or "bytes" in str(e):
                truncated_password = password[:72]
                return cls._pwd_context.hash(truncated_password)
            raise
    
    @classmethod
    def _truncate_password(cls, password: str) -> str:
        """Truncate password to max bytes (72 for bcrypt)"""
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > cls.PASSWORD_MAX_BYTES:
            # Truncate and decode, handling potential partial characters
            truncated = password_bytes[:cls.PASSWORD_MAX_BYTES]
            # Try to decode, removing incomplete UTF-8 sequences from the end
            while len(truncated) > 0:
                try:
                    return truncated.decode('utf-8')
                except UnicodeDecodeError:
                    truncated = truncated[:-1]
            return ""
        return password
    
    @classmethod
    def generate_api_key(cls) -> str:
        """Generate API key"""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def generate_api_secret(cls) -> str:
        """Generate API secret"""
        return secrets.token_urlsafe(64)
    
    @classmethod
    def generate_token(cls, length: int = 32) -> str:
        """Generate random token"""
        return secrets.token_hex(length)
    
    @classmethod
    def generate_otp(cls, digits: int = 6) -> str:
        """Generate OTP code"""
        return ''.join(random.choices(string.digits, k=digits))
    
    @classmethod
    def generate_2fa_secret(cls) -> str:
        """Generate 2FA secret"""
        import pyotp
        return pyotp.random_base32()
    
    @classmethod
    def verify_2fa_token(cls, secret: str, token: str) -> bool:
        """Verify 2FA token"""
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(token)

# Password utilities
class PasswordUtils:
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password"""
        return cls._pwd_context.hash(password)
    
    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return cls._pwd_context.verify(plain_password, hashed_password)
    
    @classmethod
    def generate_temporary_password(cls, length: int = 12) -> str:
        """Generate a temporary password"""
        chars = string.ascii_letters + string.digits + string.punctuation
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    @classmethod
    def is_strong_password(cls, password: str) -> bool:
        """Check if password meets strength requirements"""
        # At least 8 characters
        if len(password) < 8:
            return False
        # At least one uppercase letter
        if not any(c.isupper() for c in password):
            return False
        # At least one lowercase letter
        if not any(c.islower() for c in password):
            return False
        # At least one digit
        if not any(c.isdigit() for c in password):
            return False
        # At least one special character
        if not any(c in string.punctuation for c in password):
            return False
        return True

# JWT utilities
class JWTUtils:
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create JWT refresh token (valid for 30 days)"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=30)
        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except jwt.JWTError as e:
            logger.error(f"JWT decode error: {e}")
            return None

# File utilities
class FileUtils:
    @staticmethod
    async def save_upload_file(upload_file: UploadFile, destination: Path) -> Dict[str, Any]:
        """Save uploaded file to disk"""
        try:
            # Create destination directory if it doesn't exist
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            file_ext = Path(upload_file.filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = destination / unique_filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await upload_file.read()
                await f.write(content)
            
            # Get file info
            file_size = len(content)
            mime_type = upload_file.content_type or mimetypes.guess_type(upload_file.filename)[0]
            
            return {
                "success": True,
                "filename": unique_filename,
                "original_filename": upload_file.filename,
                "file_path": str(file_path),
                "file_size": file_size,
                "mime_type": mime_type
            }
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete file from disk"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    @staticmethod
    def get_file_hash(file_path: str) -> Optional[str]:
        """Calculate file hash (SHA256)"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return None
    
    @staticmethod
    def get_file_info(file_path: str) -> Optional[Dict[str, Any]]:
        """Get file information"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            stat = path.stat()
            mime_type, _ = mimetypes.guess_type(file_path)
            
            return {
                "filename": path.name,
                "file_path": str(path),
                "file_size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
                "mime_type": mime_type
            }
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Validate file extension"""
        file_ext = Path(filename).suffix.lower()
        return file_ext in allowed_extensions
    
    @staticmethod
    def validate_file_size(file_size: int, max_size: int) -> bool:
        """Validate file size"""
        return file_size <= max_size

# Email utilities
class EmailUtils:
    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: List[Dict[str, Any]] = None
    ) -> bool:
        """Send email"""
        try:
            if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD]):
                logger.warning("Email configuration missing, skipping email send")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.EMAIL_FROM
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    with open(attachment['path'], 'rb') as f:
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{attachment["filename"]}"'
                    )
                    msg.attach(part)
            
            # Send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    @staticmethod
    def send_welcome_email(user: "User") -> bool:
        """Send welcome email to new user"""
        subject = "Chào mừng đến với 7TY.VN"
        body = f"""
        Xin chào {user.full_name},
        
        Cảm ơn bạn đã đăng ký tài khoản tại 7TY.VN - Hệ thống quản trị đại lý thu hộ điện.
        
        Thông tin tài khoản của bạn:
        - Tên đăng nhập: {user.username}
        - Email: {user.email}
        
        Vui lòng đăng nhập và cập nhật thông tin cá nhân của bạn.
        
        Trân trọng,
        Đội ngũ 7TY.VN
        """
        
        html_body = f"""
        <h2>Chào mừng đến với 7TY.VN</h2>
        <p>Xin chào <strong>{user.full_name}</strong>,</p>
        <p>Cảm ơn bạn đã đăng ký tài khoản tại <strong>7TY.VN</strong> - Hệ thống quản trị đại lý thu hộ điện.</p>
        
        <h3>Thông tin tài khoản của bạn:</h3>
        <ul>
            <li><strong>Tên đăng nhập:</strong> {user.username}</li>
            <li><strong>Email:</strong> {user.email}</li>
        </ul>
        
        <p>Vui lòng đăng nhập và cập nhật thông tin cá nhân của bạn.</p>
        
        <p>Trân trọng,<br>
        Đội ngũ 7TY.VN</p>
        """
        
        return EmailUtils.send_email(user.email, subject, body, html_body)
    
    @staticmethod
    def send_password_reset_email(user: "User", reset_token: str) -> bool:
        """Send password reset email"""
        reset_url = f"https://7ty.vn/reset-password?token={reset_token}"
        
        subject = "Đặt lại mật khẩu tài khoản 7TY.VN"
        body = f"""
        Xin chào {user.full_name},
        
        Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.
        
        Để đặt lại mật khẩu, vui lòng truy cập liên kết sau:
        {reset_url}
        
        Liên kết này sẽ hết hạn sau 24 giờ.
        
        Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.
        
        Trân trọng,
        Đội ngũ 7TY.VN
        """
        
        html_body = f"""
        <h2 style="color: #0d5c63;">Đặt lại mật khẩu tài khoản 7TY.VN</h2>
        <p>Xin chào <strong>{user.full_name}</strong>,</p>
        <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.</p>
        
        <p>Để đặt lại mật khẩu, vui lòng nhấp vào liên kết sau:</p>
        <p><a href="{reset_url}" style="background: linear-gradient(135deg, #0d5c63 0%, #073b3f 100%); color: #d4af37; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Đặt lại mật khẩu</a></p>
        
        <p>Liên kết này sẽ hết hạn sau 24 giờ.</p>
        
        <p>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.</p>
        
        <p>Trân trọng,<br>
        <strong style="color: #0d5c63;">Đội ngũ 7TY.VN</strong></p>
        """
        
        return EmailUtils.send_email(user.email, subject, body, html_body)
    
    @staticmethod
    def send_notification_email(user: "User", notification: Dict[str, Any]) -> bool:
        """Send notification email"""
        subject = notification.get('subject', 'Thông báo từ 7TY.VN')
        body = notification.get('body', '')
        html_body = notification.get('html_body')
        
        return EmailUtils.send_email(user.email, subject, body, html_body)

# Formatting utilities
class FormatUtils:
    @staticmethod
    def format_currency(amount: Union[int, float, Decimal], currency: str = "VND") -> str:
        """Format currency"""
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        
        # Round to nearest whole number
        amount = amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        
        # Format with thousand separators
        formatted = f"{amount:,.0f}".replace(",", ".")
        
        return f"{formatted} {currency}"
    
    @staticmethod
    def format_date(date_obj: Union[datetime, date], format_str: str = "%d/%m/%Y") -> str:
        """Format date"""
        if isinstance(date_obj, datetime):
            return date_obj.strftime(format_str)
        elif isinstance(date_obj, date):
            return date_obj.strftime(format_str)
        else:
            return str(date_obj)
    
    @staticmethod
    def format_datetime(datetime_obj: datetime, format_str: str = "%d/%m/%Y %H:%M") -> str:
        """Format datetime"""
        return datetime_obj.strftime(format_str)
    
    @staticmethod
    def format_relative_time(datetime_obj: datetime) -> str:
        """Format relative time (e.g., "2 giờ trước")"""
        now = datetime.utcnow()
        diff = now - datetime_obj
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} năm trước"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} tháng trước"
        elif diff.days > 0:
            return f"{diff.days} ngày trước"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} giờ trước"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} phút trước"
        else:
            return "Vừa xong"
    
    @staticmethod
    def format_phone_number(phone: str) -> str:
        """Format phone number"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Format based on length
        if len(digits) == 10:
            return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
        elif len(digits) == 11:
            return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
        else:
            return phone
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix

# Validation utilities
class ValidationUtils:
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number"""
        pattern = r'^\+?[0-9\s\-\(\)]{10,}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, List[str]]:
        """Validate password strength"""
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'[0-9]', password):
            errors.append("Password must contain at least one number")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_vietnamese_name(name: str) -> bool:
        """Validate Vietnamese name"""
        pattern = r'^[A-Za-zÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠ-ỹ\s]+$'
        return bool(re.match(pattern, name))
    
    @staticmethod
    def validate_identity_card(id_card: str) -> bool:
        """Validate Vietnamese identity card (9 or 12 digits)"""
        pattern = r'^\d{9}$|^\d{12}$'
        return bool(re.match(pattern, id_card))
    
    @staticmethod
    def validate_bill_period(period: str) -> bool:
        """Validate bill period format (YYYY-MM)"""
        pattern = r'^\d{4}-(0[1-9]|1[0-2])$'
        if not re.match(pattern, period):
            return False
        
        # Check if date is not in the future
        year, month = map(int, period.split('-'))
        current_date = datetime.utcnow().date()
        period_date = date(year, month, 1)
        
        return period_date <= current_date

# Calculation utilities
class CalculationUtils:
    @staticmethod
    def calculate_commission(bill_amount: Decimal, commission_rate: Decimal) -> Decimal:
        """Calculate commission amount"""
        commission = (bill_amount * commission_rate / 100)
        return commission.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_vat_amount(amount: Decimal, vat_rate: Decimal = Decimal('10')) -> Decimal:
        """Calculate VAT amount"""
        vat = (amount * vat_rate / 100)
        return vat.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_discount(amount: Decimal, discount_rate: Decimal) -> Decimal:
        """Calculate discount amount"""
        discount = (amount * discount_rate / 100)
        return discount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def round_amount(amount: Decimal) -> Decimal:
        """Round amount to nearest 1000"""
        return (amount / 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * 1000

# Export utilities
class ExportUtils:
    @staticmethod
    def export_to_excel(data: List[Dict[str, Any]], filename: str) -> str:
        """Export data to Excel file"""
        try:
            export_dir = Path(settings.UPLOAD_FOLDER) / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            file_path = export_dir / f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create workbook
            workbook = xlsxwriter.Workbook(str(file_path))
            worksheet = workbook.add_worksheet()
            
            # Write headers
            if data:
                headers = list(data[0].keys())
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header)
                
                # Write data
                for row, item in enumerate(data, start=1):
                    for col, key in enumerate(headers):
                        value = item.get(key, '')
                        worksheet.write(row, col, value)
            
            workbook.close()
            
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            raise
    
    @staticmethod
    def export_to_csv(data: List[Dict[str, Any]], filename: str) -> str:
        """Export data to CSV file"""
        try:
            export_dir = Path(settings.UPLOAD_FOLDER) / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            file_path = export_dir / f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                if data:
                    fieldnames = list(data[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
            
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise
    
    @staticmethod
    def generate_qr_code(data: str, size: int = 10) -> str:
        """Generate QR code as base64 string"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=size,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return ""

# Data import utilities
class ImportUtils:
    @staticmethod
    async def import_bills_from_excel(file_path: str, db: Session, created_by_id: int) -> Dict[str, Any]:
        """Import bills from Excel file"""
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Validate required columns
            required_columns = ['customer_code', 'customer_name', 'period', 'total_amount']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    "success": False,
                    "error": f"Missing required columns: {', '.join(missing_columns)}"
                }
            
            imported = 0
            skipped = 0
            errors = []
            bill_codes = []
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    # Generate bill code
                    bill_code = f"BILL{datetime.now().strftime('%Y%m%d')}{imported + 1:06d}"
                    
                    # Create bill record
                    bill = Bill(
                        bill_code=bill_code,
                        customer_code=str(row['customer_code']),
                        customer_name=str(row['customer_name']),
                        customer_address=row.get('customer_address'),
                        customer_phone=row.get('customer_phone'),
                        period=str(row['period']),
                        total_amount=Decimal(str(row['total_amount'])),
                        electricity_amount=Decimal(str(row.get('electricity_amount', row['total_amount']))),
                        vat_amount=Decimal(str(row.get('vat_amount', 0))),
                        other_fees=Decimal(str(row.get('other_fees', 0))),
                        consumption=Decimal(str(row['consumption'])) if 'consumption' in row else None,
                        status='in_stock',
                        created_by_id=created_by_id
                    )
                    
                    db.add(bill)
                    db.commit()
                    
                    imported += 1
                    bill_codes.append(bill_code)
                    
                except Exception as e:
                    skipped += 1
                    errors.append(f"Row {index + 2}: {str(e)}")
                    db.rollback()
                    continue
            
            return {
                "success": True,
                "total": len(df),
                "imported": imported,
                "skipped": skipped,
                "errors": errors,
                "bill_codes": bill_codes
            }
            
        except Exception as e:
            logger.error(f"Error importing bills from Excel: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def import_customers_from_csv(file_path: str, db: Session, agent_id: Optional[int] = None) -> Dict[str, Any]:
        """Import customers from CSV file"""
        try:
            # Read CSV file
            df = pd.read_csv(file_path)
            
            # Validate required columns
            required_columns = ['customer_code', 'full_name', 'address']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    "success": False,
                    "error": f"Missing required columns: {', '.join(missing_columns)}"
                }
            
            imported = 0
            skipped = 0
            errors = []
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    # Check if customer already exists
                    existing = db.query(Customer).filter(
                        Customer.customer_code == str(row['customer_code'])
                    ).first()
                    
                    if existing:
                        skipped += 1
                        errors.append(f"Row {index + 2}: Customer code already exists")
                        continue
                    
                    # Create customer record
                    customer = Customer(
                        customer_code=str(row['customer_code']),
                        full_name=str(row['full_name']),
                        address=str(row['address']),
                        phone=row.get('phone'),
                        email=row.get('email'),
                        evn_customer_code=row.get('evn_customer_code'),
                        meter_code=row.get('meter_code'),
                        agent_id=agent_id
                    )
                    
                    db.add(customer)
                    db.commit()
                    
                    imported += 1
                    
                except Exception as e:
                    skipped += 1
                    errors.append(f"Row {index + 2}: {str(e)}")
                    db.rollback()
                    continue
            
            return {
                "success": True,
                "total": len(df),
                "imported": imported,
                "skipped": skipped,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error importing customers from CSV: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Cache utilities
class CacheUtils:
    _cache = {}
    _cache_ttl = {}
    
    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300) -> None:
        """Set cache value with TTL (seconds)"""
        cls._cache[key] = value
        cls._cache_ttl[key] = datetime.utcnow() + timedelta(seconds=ttl)
    
    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Get cache value"""
        if key in cls._cache:
            # Check TTL
            if key in cls._cache_ttl and cls._cache_ttl[key] > datetime.utcnow():
                return cls._cache[key]
            else:
                # Remove expired cache
                cls.delete(key)
        return None
    
    @classmethod
    def delete(cls, key: str) -> None:
        """Delete cache value"""
        cls._cache.pop(key, None)
        cls._cache_ttl.pop(key, None)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all cache"""
        cls._cache.clear()
        cls._cache_ttl.clear()
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "total_items": len(cls._cache),
            "expired_items": len([k for k, v in cls._cache_ttl.items() if v <= datetime.utcnow()]),
            "memory_usage": f"{sum(len(str(v)) for v in cls._cache.values())} bytes"
        }

# WebSocket utilities
class WebSocketManager:
    def __init__(self):
        self.active_connections = {}
    
    async def connect(self, websocket, user_id: int):
        """Handle new WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user {user_id}")
    
    async def disconnect(self, user_id: int):
        """Handle WebSocket disconnection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                await self.disconnect(user_id)
    
    async def broadcast(self, message: dict, exclude_user_ids: List[int] = None):
        """Broadcast message to all connected users"""
        exclude_user_ids = exclude_user_ids or []
        
        for user_id, websocket in list(self.active_connections.items()):
            if user_id not in exclude_user_ids:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting WebSocket message: {e}")
                    await self.disconnect(user_id)

# Rate limiter
class RateLimiter:
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed based on rate limit"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)
        
        # Clean old requests
        if key in self.requests:
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if req_time > window_start
            ]
        else:
            self.requests[key] = []
        
        # Check limit
        if len(self.requests[key]) < limit:
            self.requests[key].append(now)
            return True
        
        return False
    
    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)
        
        if key in self.requests:
            recent_requests = [
                req_time for req_time in self.requests[key]
                if req_time > window_start
            ]
            return max(0, limit - len(recent_requests))
        
        return limit

# Background task utilities
class BackgroundTaskUtils:
    @staticmethod
    async def process_background_task(task_func, *args, **kwargs):
        """Process background task"""
        try:
            await task_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Background task error: {e}")

# Mock external APIs
class ExternalAPIs:
    @staticmethod
    async def verify_evn_bill(bill_code: str, customer_code: str) -> Dict[str, Any]:
        """Mock EVN bill verification"""
        # In production, this would call the actual EVN API
        await asyncio.sleep(0.1)  # Simulate API call
        
        return {
            "success": True,
            "valid": True,
            "amount": 100000,
            "due_date": (datetime.utcnow() + timedelta(days=15)).strftime("%Y-%m-%d"),
            "status": "unpaid"
        }
    
    @staticmethod
    async def process_payment(amount: Decimal, payment_method: str) -> Dict[str, Any]:
        """Mock payment processing"""
        await asyncio.sleep(0.2)  # Simulate API call
        
        return {
            "success": True,
            "transaction_id": f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}",
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def send_sms(phone: str, message: str) -> bool:
        """Mock SMS sending"""
        await asyncio.sleep(0.1)  # Simulate API call
        
        logger.info(f"SMS sent to {phone}: {message}")
        return True

# Health check utilities
class HealthCheckUtils:
    @staticmethod
    def check_database_health(db: Session) -> Dict[str, Any]:
        """Check database health"""
        try:
            # Try to execute a simple query
            db.execute("SELECT 1")
            return {
                "status": "healthy",
                "response_time": 0.001
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @staticmethod
    def check_disk_space() -> Dict[str, Any]:
        """Check disk space"""
        import shutil
        
        try:
            total, used, free = shutil.disk_usage("/")
            return {
                "total_gb": total / (1024**3),
                "used_gb": used / (1024**3),
                "free_gb": free / (1024**3),
                "free_percent": (free / total) * 100
            }
        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """Get system statistics"""
        import psutil
        import platform
        
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else None,
                "network_io": psutil.net_io_counters()._asdict(),
                "boot_time": datetime.fromtimestamp(psutil.boot_time()),
                "platform": platform.platform(),
                "python_version": platform.python_version()
            }
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {"error": str(e)}

# Convenience imports for backward compatibility
verify_password = SecurityUtils.verify_password
get_password_hash = SecurityUtils.get_password_hash
create_access_token = JWTUtils.create_access_token
decode_token = JWTUtils.decode_token
format_currency = FormatUtils.format_currency
format_date = FormatUtils.format_date
format_datetime = FormatUtils.format_datetime
validate_email = ValidationUtils.validate_email
validate_phone = ValidationUtils.validate_phone
validate_password = ValidationUtils.validate_password
calculate_commission = CalculationUtils.calculate_commission

# Additional helper functions
def generate_bill_code() -> str:
    """Generate a unique bill code"""
    import time
    timestamp = int(time.time() * 1000)
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"BILL{timestamp}{random_part}"

def generate_transaction_code() -> str:
    """Generate a unique transaction code"""
    import time
    timestamp = int(time.time() * 1000)
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"TXN{timestamp}{random_part}"

def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """Encrypt data using Fernet (AES-128)"""
    from cryptography.fernet import Fernet
    if key is None:
        key = settings.SECRET_KEY.encode()[:32].ljust(32)
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
    f = Fernet(fernet_key)
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> str:
    """Decrypt encrypted data"""
    from cryptography.fernet import Fernet
    if key is None:
        key = settings.SECRET_KEY.encode()[:32].ljust(32)
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
    f = Fernet(fernet_key)
    return f.decrypt(encrypted_data.encode()).decode()

def validate_vietnamese_phone(phone: str) -> bool:
    """Validate Vietnamese phone number"""
    # Vietnamese phone numbers: 10 digits starting with 0
    pattern = r'^0[1-9]\d{8}$'
    return bool(re.match(pattern, phone))

def generate_report(data: List[Dict[str, Any]], report_type: str = 'summary') -> Dict[str, Any]:
    """Generate a report from data"""
    if not data:
        return {"summary": {}, "details": []}
    
    if report_type == 'summary':
        return {
            "total_records": len(data),
            "summary": {}
        }
    elif report_type == 'detailed':
        return {
            "total_records": len(data),
            "details": data
        }
    
    return {"data": data}

def backup_database(backup_path: Optional[str] = None) -> Dict[str, Any]:
    """Backup the database"""
    import shutil
    from datetime import datetime
    
    try:
        if backup_path is None:
            backup_path = settings.UPLOAD_FOLDER or "./backups"
        
        Path(backup_path).mkdir(parents=True, exist_ok=True)
        
        # For SQLite
        if "sqlite" in settings.DATABASE_URL:
            db_file = settings.DATABASE_URL.split("///")[-1]
            if not Path(db_file).exists():
                return {"success": False, "error": "Database file not found"}
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_path}/backup_{timestamp}.db"
            shutil.copy2(db_file, backup_file)
            
            return {
                "success": True,
                "backup_file": backup_file,
                "timestamp": timestamp
            }
        
        return {"success": False, "error": "Database type not supported"}
    
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return {"success": False, "error": str(e)}

def restore_database(backup_file: str) -> Dict[str, Any]:
    """Restore database from backup"""
    import shutil
    
    try:
        if not Path(backup_file).exists():
            return {"success": False, "error": "Backup file not found"}
        
        if "sqlite" in settings.DATABASE_URL:
            db_file = settings.DATABASE_URL.split("///")[-1]
            shutil.copy2(backup_file, db_file)
            
            return {
                "success": True,
                "message": "Database restored successfully"
            }
        
        return {"success": False, "error": "Database type not supported"}
    
    except Exception as e:
        logger.error(f"Restore error: {e}")
        return {"success": False, "error": str(e)}

def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    import platform
    import psutil
    
    try:
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {}

def generate_unique_filename(extension: str = "") -> str:
    """Generate a unique filename"""
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    return f"{timestamp}_{random_part}{extension}"

def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """Validate file type"""
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions

def validate_file_size(file_size: int, max_size: int) -> bool:
    """Validate file size"""
    return file_size <= max_size

def calculate_file_hash(file_path: str) -> str:
    """Calculate file hash (SHA256)"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def export_to_excel(data: List[Dict[str, Any]], filename: str, sheet_name: str = "Data") -> str:
    """Export data to Excel file"""
    try:
        import xlsxwriter
        export_dir = Path(settings.UPLOAD_FOLDER) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(export_dir / filename) if not filename.endswith('.xlsx') else str(export_dir / filename)
        if not output_path.endswith('.xlsx'):
            output_path += '.xlsx'
        
        workbook = xlsxwriter.Workbook(output_path)
        worksheet = workbook.add_worksheet(sheet_name)
        
        if data:
            headers = list(data[0].keys())
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)
            
            for row, item in enumerate(data, start=1):
                for col, header in enumerate(headers):
                    worksheet.write(row, col, item.get(header, ""))
        
        workbook.close()
        return output_path
    except Exception as e:
        logger.error(f"Export to Excel error: {e}")
        raise

def export_to_csv(data: List[Dict[str, Any]], filename: str) -> str:
    """Export data to CSV file"""
    try:
        export_dir = Path(settings.UPLOAD_FOLDER) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(export_dir / filename) if not filename.endswith('.csv') else str(export_dir / filename)
        if not output_path.endswith('.csv'):
            output_path += '.csv'
        
        if not data:
            return output_path
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        return output_path
    except Exception as e:
        logger.error(f"Export to CSV error: {e}")
        raise