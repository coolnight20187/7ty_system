import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Optional
import logging
from config import Config
import os

logger = logging.getLogger(__name__)

def send_email(
    to_email: str,
    subject: str,
    body: str,
    html: bool = True,
    cc: List[str] = None,
    bcc: List[str] = None,
    attachments: List[str] = None
) -> bool:
    """
    Gửi email sử dụng SMTP
    
    Args:
        to_email: Email người nhận
        subject: Tiêu đề email
        body: Nội dung email
        html: True nếu nội dung là HTML
        cc: Danh sách email CC
        bcc: Danh sách email BCC
        attachments: Danh sách đường dẫn file đính kèm
    
    Returns:
        bool: True nếu gửi thành công, False nếu thất bại
    """
    try:
        # Kiểm tra cấu hình email
        if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured. Email will not be sent.")
            return False
        
        # Tạo message
        msg = MIMEMultipart()
        msg['From'] = Config.FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = ', '.join(cc)
        
        # Thêm nội dung email
        if html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        # Thêm đính kèm
        if attachments:
            for attachment in attachments:
                if os.path.exists(attachment):
                    with open(attachment, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(attachment))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                        msg.attach(part)
        
        # Kết nối SMTP server
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()  # Bật TLS
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            
            # Gửi email
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error while sending email: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

def send_template_email(
    to_email: str,
    template_name: str,
    template_vars: dict,
    subject: Optional[str] = None,
    cc: List[str] = None,
    bcc: List[str] = None
) -> bool:
    """
    Gửi email sử dụng template
    
    Args:
        to_email: Email người nhận
        template_name: Tên template (tên file trong thư mục templates/emails)
        template_vars: Biến template
        subject: Tiêu đề email (nếu None sẽ lấy từ template)
        cc: Danh sách email CC
        bcc: Danh sách email BCC
    
    Returns:
        bool: True nếu gửi thành công, False nếu thất bại
    """
    try:
        # Đọc template file
        template_path = os.path.join("templates", "emails", f"{template_name}.html")
        
        if not os.path.exists(template_path):
            logger.error(f"Template not found: {template_path}")
            return False
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Thay thế biến template
        for key, value in template_vars.items():
            placeholder = f"{{{{ {key} }}}}"
            template_content = template_content.replace(placeholder, str(value))
        
        # Mặc định tiêu đề nếu không có
        if not subject:
            # Tìm tiêu đề trong template (thẻ <title>)
            import re
            title_match = re.search(r'<title>(.*?)</title>', template_content, re.IGNORECASE)
            subject = title_match.group(1) if title_match else "Thông báo từ 7TY.VN"
        
        # Gửi email
        return send_email(to_email, subject, template_content, html=True, cc=cc, bcc=bcc)
        
    except Exception as e:
        logger.error(f"Error sending template email: {str(e)}")
        return False

def send_bulk_emails(
    emails: List[str],
    subject: str,
    body: str,
    html: bool = True,
    attachments: List[str] = None
) -> dict:
    """
    Gửi email hàng loạt
    
    Args:
        emails: Danh sách email người nhận
        subject: Tiêu đề email
        body: Nội dung email
        html: True nếu nội dung là HTML
        attachments: Danh sách đường dẫn file đính kèm
    
    Returns:
        dict: Kết quả gửi email (success_count, failed_count, failed_emails)
    """
    results = {
        'success_count': 0,
        'failed_count': 0,
        'failed_emails': []
    }
    
    for email in emails:
        success = send_email(email, subject, body, html=html, attachments=attachments)
        if success:
            results['success_count'] += 1
        else:
            results['failed_count'] += 1
            results['failed_emails'].append(email)
    
    logger.info(f"Bulk email sent: {results['success_count']} success, {results['failed_count']} failed")
    return results

def send_verification_email(email: str, verification_code: str, user_name: str) -> bool:
    """
    Gửi email xác thực tài khoản
    
    Args:
        email: Email người nhận
        verification_code: Mã xác thực
        user_name: Tên người dùng
    
    Returns:
        bool: True nếu gửi thành công
    """
    subject = "Xác thực tài khoản 7TY.VN"
    
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Xác thực tài khoản</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background-color: #f9f9f9; }}
            .code {{ font-size: 24px; font-weight: bold; color: #4CAF50; text-align: center; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Xác thực tài khoản 7TY.VN</h1>
            </div>
            <div class="content">
                <p>Xin chào <strong>{user_name}</strong>,</p>
                <p>Cảm ơn bạn đã đăng ký tài khoản tại 7TY.VN. Để hoàn tất đăng ký, vui lòng sử dụng mã xác thực dưới đây:</p>
                <div class="code">{verification_code}</div>
                <p>Mã xác thực có hiệu lực trong 24 giờ.</p>
                <p>Nếu bạn không yêu cầu xác thực này, vui lòng bỏ qua email này.</p>
            </div>
            <div class="footer">
                <p>© {datetime.now().year} 7TY.VN - Hệ thống quản lý đại lý thu hộ hóa đơn điện</p>
                <p>Địa chỉ: {Config.COMPANY_ADDRESS}</p>
                <p>Hotline: {Config.SUPPORT_PHONE} | Email: {Config.SUPPORT_EMAIL}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(email, subject, body, html=True)

def send_password_reset_email(email: str, reset_code: str, user_name: str) -> bool:
    """
    Gửi email đặt lại mật khẩu
    
    Args:
        email: Email người nhận
        reset_code: Mã đặt lại mật khẩu
        user_name: Tên người dùng
    
    Returns:
        bool: True nếu gửi thành công
    """
    subject = "Đặt lại mật khẩu 7TY.VN"
    
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Đặt lại mật khẩu</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background-color: #f9f9f9; }}
            .code {{ font-size: 24px; font-weight: bold; color: #2196F3; text-align: center; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Đặt lại mật khẩu</h1>
            </div>
            <div class="content">
                <p>Xin chào <strong>{user_name}</strong>,</p>
                <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.</p>
                <p>Để đặt lại mật khẩu, vui lòng sử dụng mã dưới đây:</p>
                <div class="code">{reset_code}</div>
                <p>Mã có hiệu lực trong 1 giờ.</p>
                <p>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.</p>
                <p>Để bảo vệ tài khoản của bạn, không chia sẻ mã này với bất kỳ ai.</p>
            </div>
            <div class="footer">
                <p>© {datetime.now().year} 7TY.VN - Hệ thống quản lý đại lý thu hộ hóa đơn điện</p>
                <p>Hotline: {Config.SUPPORT_PHONE} | Email: {Config.SUPPORT_EMAIL}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(email, subject, body, html=True)

def send_notification_email(
    email: str,
    title: str,
    message: str,
    notification_type: str = "info"
) -> bool:
    """
    Gửi email thông báo
    
    Args:
        email: Email người nhận
        title: Tiêu đề thông báo
        message: Nội dung thông báo
        notification_type: Loại thông báo (info, success, warning, error)
    
    Returns:
        bool: True nếu gửi thành công
    """
    # Màu sắc theo loại thông báo
    colors = {
        "info": "#2196F3",
        "success": "#4CAF50",
        "warning": "#FF9800",
        "error": "#F44336"
    }
    
    color = colors.get(notification_type, "#2196F3")
    
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; background-color: #f9f9f9; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                {message}
            </div>
            <div class="footer">
                <p>© {datetime.now().year} 7TY.VN - Hệ thống quản lý đại lý thu hộ hóa đơn điện</p>
                <p>Hotline: {Config.SUPPORT_PHONE} | Email: {Config.SUPPORT_EMAIL}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(email, title, body, html=True)

def test_email_connection() -> bool:
    """
    Kiểm tra kết nối SMTP
    
    Returns:
        bool: True nếu kết nối thành công
    """
    try:
        if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
            logger.error("SMTP credentials not configured")
            return False
        
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        
        logger.info("SMTP connection test successful")
        return True
        
    except Exception as e:
        logger.error(f"SMTP connection test failed: {str(e)}")
        return False

async def send_system_notification(
    title: str,
    message: str,
    notification_type: str = "system",
    recipients: list = None
) -> bool:
    """
    Gửi thông báo hệ thống
    """
    try:
        if recipients is None:
            recipients = []
        
        # Log the notification
        logger.info(f"System notification: {title} - {message}")
        
        # Send to all recipients if available
        for recipient in recipients:
            await send_notification_email(recipient, title, message, notification_type)
        
        return True
    except Exception as e:
        logger.error(f"Failed to send system notification: {e}")
        return False

# Import datetime ở cuối để tránh circular import
from datetime import datetime