"""
Email Reader Service - Đọc email ngân hàng để nhận biết giao dịch
Hỗ trợ: Gmail, Outlook, Yahoo và các email server IMAP khác
"""

import imaplib
import email
from email.header import decode_header
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import json
import asyncio
from decimal import Decimal

logger = logging.getLogger(__name__)

@dataclass
class BankTransaction:
    """Thông tin giao dịch parse từ email"""
    bank_code: str
    amount: float
    content: str
    transaction_type: str  # 'credit' hoặc 'debit'
    account_number: str
    balance: Optional[float] = None
    transaction_time: Optional[datetime] = None
    transaction_id: Optional[str] = None
    raw_content: str = ""


class EmailReaderService:
    """Service đọc email ngân hàng tự động"""
    
    # Mapping email sender -> bank code
    BANK_EMAIL_SENDERS = {
        # MB Bank
        'mbbank.com.vn': 'MB',
        'notification@mbbank.com.vn': 'MB',
        'ebanking@mbbank.com.vn': 'MB',
        # Vietcombank
        'vietcombank.com.vn': 'VCB',
        'vcb.com.vn': 'VCB',
        'notification@vietcombank.com.vn': 'VCB',
        # Techcombank
        'techcombank.com.vn': 'TCB',
        'notification@techcombank.com.vn': 'TCB',
        # ACB
        'acb.com.vn': 'ACB',
        'notification@acb.com.vn': 'ACB',
        # Vietinbank
        'vietinbank.vn': 'CTG',
        'notification@vietinbank.vn': 'CTG',
        # BIDV
        'bidv.com.vn': 'BIDV',
        'notification@bidv.com.vn': 'BIDV',
        # Sacombank
        'sacombank.com.vn': 'STB',
        'notification@sacombank.com.vn': 'STB',
        # TPBank
        'tpbank.vn': 'TPB',
        'notification@tpbank.vn': 'TPB',
        # VPBank
        'vpbank.com.vn': 'VPB',
        'notification@vpbank.com.vn': 'VPB',
        # Agribank
        'agribank.com.vn': 'AGR',
        'notification@agribank.com.vn': 'AGR',
        # Momo
        'momo.vn': 'MOMO',
        'notification@momo.vn': 'MOMO',
    }
    
    # IMAP server configs
    IMAP_SERVERS = {
        'gmail.com': ('imap.gmail.com', 993),
        'googlemail.com': ('imap.gmail.com', 993),
        'outlook.com': ('outlook.office365.com', 993),
        'hotmail.com': ('outlook.office365.com', 993),
        'yahoo.com': ('imap.mail.yahoo.com', 993),
        'default': ('imap.gmail.com', 993)
    }
    
    def __init__(self, email_address: str, password: str, imap_server: str = None, imap_port: int = None):
        """
        Khởi tạo Email Reader
        
        Args:
            email_address: Địa chỉ email
            password: Mật khẩu email hoặc App Password
            imap_server: IMAP server (tự động detect nếu không cung cấp)
            imap_port: IMAP port (mặc định 993 cho SSL)
        """
        self.email_address = email_address
        self.password = password
        
        # Auto detect IMAP server
        if imap_server:
            self.imap_server = imap_server
            self.imap_port = imap_port or 993
        else:
            domain = email_address.split('@')[-1].lower()
            server_config = self.IMAP_SERVERS.get(domain, self.IMAP_SERVERS['default'])
            self.imap_server = server_config[0]
            self.imap_port = server_config[1]
        
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.is_connected = False
    
    def connect(self) -> bool:
        """Kết nối đến email server"""
        self.last_error = None
        try:
            logger.info(f"Connecting to {self.imap_server}:{self.imap_port} for {self.email_address}")
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.email_address, self.password)
            self.is_connected = True
            logger.info(f"Connected to email: {self.email_address}")
            return True
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            logger.error(f"IMAP login failed for {self.email_address}: {error_msg}")
            self.is_connected = False
            # Parse common errors
            if 'AUTHENTICATIONFAILED' in error_msg or 'Invalid credentials' in error_msg.lower():
                self.last_error = 'Sai mật khẩu hoặc App Password. Với Gmail, cần dùng App Password (16 ký tự).'
            elif 'Web login required' in error_msg:
                self.last_error = 'Gmail yêu cầu bật "Less secure apps" hoặc dùng App Password.'
            else:
                self.last_error = f'Lỗi đăng nhập IMAP: {error_msg}'
            return False
        except ConnectionRefusedError:
            self.last_error = f'Không thể kết nối đến server {self.imap_server}:{self.imap_port}'
            logger.error(self.last_error)
            self.is_connected = False
            return False
        except TimeoutError:
            self.last_error = 'Timeout khi kết nối. Kiểm tra kết nối mạng.'
            logger.error(self.last_error)
            self.is_connected = False
            return False
        except Exception as e:
            self.last_error = f'Lỗi kết nối: {str(e)}'
            logger.error(f"Connection error for {self.email_address}: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Ngắt kết nối"""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None
            self.is_connected = False
    
    def _decode_header_value(self, value) -> str:
        """Decode email header"""
        if value is None:
            return ""
        decoded_parts = decode_header(value)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                result += part
        return result
    
    def _get_email_body(self, msg) -> str:
        """Lấy nội dung email"""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
                    except:
                        pass
                elif content_type == "text/html" and "attachment" not in content_disposition and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html_body = payload.decode(charset, errors='ignore')
                        # Strip HTML tags
                        body = re.sub(r'<[^>]+>', ' ', html_body)
                        body = re.sub(r'\s+', ' ', body).strip()
                    except:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
                
                if msg.get_content_type() == "text/html":
                    body = re.sub(r'<[^>]+>', ' ', body)
                    body = re.sub(r'\s+', ' ', body).strip()
            except:
                pass
        
        return body
    
    def _detect_bank_from_sender(self, sender: str) -> Optional[str]:
        """Detect bank code từ email sender"""
        sender_lower = sender.lower()
        
        for email_pattern, bank_code in self.BANK_EMAIL_SENDERS.items():
            if email_pattern in sender_lower:
                return bank_code
        
        return None
    
    def _parse_transaction_from_email(self, subject: str, body: str, sender: str) -> Optional[BankTransaction]:
        """Parse thông tin giao dịch từ email"""
        
        bank_code = self._detect_bank_from_sender(sender)
        if not bank_code:
            return None
        
        content = f"{subject}\n{body}"
        content_upper = content.upper()
        
        # Detect transaction type
        credit_keywords = ['+', 'NHẬN', 'CỘNG', 'VÀO TÀI KHOẢN', 'GHI CÓ', 'CREDITED', 
                          'TIỀN VÀO', 'NHẬN ĐƯỢC', 'CHUYỂN ĐẾN', 'RECEIVED']
        debit_keywords = ['-', 'TRỪ', 'CHUYỂN KHOẢN ĐI', 'GHI NỢ', 'DEBITED', 
                         'TIỀN RA', 'THANH TOÁN', 'CHUYỂN ĐI']
        
        transaction_type = None
        for kw in credit_keywords:
            if kw in content_upper:
                transaction_type = 'credit'
                break
        
        if not transaction_type:
            for kw in debit_keywords:
                if kw in content_upper:
                    transaction_type = 'debit'
                    break
        
        if not transaction_type:
            return None
        
        # Parse amount - tìm số tiền
        amount_patterns = [
            r'[+\-]?\s*([\d,\.]+)\s*(?:VND|VNĐ|đ|dong|đồng)',
            r'Số tiền[:\s]*([\d,\.]+)',
            r'Amount[:\s]*([\d,\.]+)',
            r'([\d,\.]+)\s*(?:VND|VNĐ)',
            r'(?:cộng|trừ|nhận|gửi)[:\s]*([\d,\.]+)',
        ]
        
        amount = None
        for pattern in amount_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace('.', '')
                try:
                    amount = float(amount_str)
                    if amount > 0:
                        break
                except:
                    pass
        
        if not amount or amount <= 0:
            return None
        
        # Parse account number
        account_patterns = [
            r'(?:TK|Tài khoản|Account)[:\s]*(\d{6,20})',
            r'(\d{10,20})',
        ]
        
        account_number = ""
        for pattern in account_patterns:
            match = re.search(pattern, content)
            if match:
                account_number = match.group(1)
                break
        
        # Parse nội dung chuyển khoản
        transfer_content = ""
        content_patterns = [
            r'(?:ND|Nội dung|Content|Memo)[:\s]*([^\n\r]+)',
            r'(?:NAP|NAPTIEN|TOPUP)\s+(\w+)',
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                transfer_content = match.group(1).strip()
                break
        
        if not transfer_content:
            transfer_content = content[:200]
        
        # Parse balance
        balance = None
        balance_patterns = [
            r'(?:Số dư|Balance|SD)[:\s]*([\d,\.]+)',
        ]
        
        for pattern in balance_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    balance = float(match.group(1).replace(',', '').replace('.', ''))
                except:
                    pass
                break
        
        return BankTransaction(
            bank_code=bank_code,
            amount=amount,
            content=transfer_content,
            transaction_type=transaction_type,
            account_number=account_number,
            balance=balance,
            raw_content=content[:500]
        )
    
    def fetch_bank_emails(self, since_hours: int = 24, mark_as_read: bool = False) -> List[BankTransaction]:
        """
        Fetch và parse email ngân hàng
        
        Args:
            since_hours: Lấy email trong X giờ gần đây
            mark_as_read: Đánh dấu đã đọc sau khi xử lý
            
        Returns:
            Danh sách giao dịch được parse
        """
        if not self.is_connected:
            if not self.connect():
                return []
        
        transactions = []
        
        try:
            # Select inbox
            self.connection.select('INBOX')
            
            # Build search criteria
            since_date = (datetime.now() - timedelta(hours=since_hours)).strftime('%d-%b-%Y')
            
            # Search for emails from bank senders
            bank_domains = set()
            for sender in self.BANK_EMAIL_SENDERS.keys():
                if '@' in sender:
                    domain = sender.split('@')[1]
                else:
                    domain = sender
                bank_domains.add(domain)
            
            # Search unseen emails since date
            search_criteria = f'(SINCE {since_date} UNSEEN)'
            
            status, messages = self.connection.search(None, search_criteria)
            
            if status != 'OK':
                logger.error("Failed to search emails")
                return []
            
            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} unread emails since {since_date}")
            
            for email_id in email_ids[-50:]:  # Limit to 50 emails
                try:
                    status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK':
                        continue
                    
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Get sender
                    sender = self._decode_header_value(msg.get('From', ''))
                    
                    # Check if from bank
                    is_bank_email = False
                    for domain in bank_domains:
                        if domain in sender.lower():
                            is_bank_email = True
                            break
                    
                    if not is_bank_email:
                        continue
                    
                    # Get subject and body
                    subject = self._decode_header_value(msg.get('Subject', ''))
                    body = self._get_email_body(msg)
                    
                    # Parse transaction
                    transaction = self._parse_transaction_from_email(subject, body, sender)
                    
                    if transaction:
                        # Get email date
                        date_str = msg.get('Date', '')
                        try:
                            transaction.transaction_time = email.utils.parsedate_to_datetime(date_str)
                        except:
                            transaction.transaction_time = datetime.now()
                        
                        # Generate transaction ID from email ID
                        transaction.transaction_id = f"EMAIL_{email_id.decode()}"
                        
                        transactions.append(transaction)
                        logger.info(f"Parsed transaction: {transaction.bank_code} {transaction.transaction_type} {transaction.amount}")
                        
                        # Mark as read if requested
                        if mark_as_read:
                            self.connection.store(email_id, '+FLAGS', '\\Seen')
                
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
        
        return transactions
    
    def test_connection(self) -> Dict[str, Any]:
        """Test kết nối email"""
        try:
            if self.connect():
                self.connection.select('INBOX')
                status, messages = self.connection.search(None, 'ALL')
                total_emails = len(messages[0].split()) if status == 'OK' else 0
                
                self.disconnect()
                
                return {
                    'success': True,
                    'message': 'Kết nối thành công',
                    'email': self.email_address,
                    'server': self.imap_server,
                    'total_emails': total_emails
                }
            else:
                return {
                    'success': False,
                    'message': getattr(self, 'last_error', None) or 'Không thể kết nối. Kiểm tra lại email và mật khẩu.',
                    'email': self.email_address,
                    'server': self.imap_server
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}',
                'email': self.email_address,
                'server': self.imap_server
            }


class EmailReaderManager:
    """Manager để quản lý nhiều email reader"""
    
    _instance = None
    _readers: Dict[str, EmailReaderService] = {}
    _config: Dict[str, Any] = {}
    _is_running: bool = False
    _check_interval: int = 60  # seconds
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def add_email_config(self, email_address: str, password: str, 
                         imap_server: str = None, imap_port: int = None,
                         bank_account: str = None) -> bool:
        """Thêm cấu hình email"""
        try:
            reader = EmailReaderService(email_address, password, imap_server, imap_port)
            
            # Test connection
            if reader.connect():
                reader.disconnect()
                self._readers[email_address] = reader
                self._config[email_address] = {
                    'email': email_address,
                    'password': password,
                    'imap_server': imap_server or reader.imap_server,
                    'imap_port': imap_port or reader.imap_port,
                    'bank_account': bank_account,
                    'enabled': True
                }
                logger.info(f"Added email config: {email_address}")
                return True
            else:
                logger.error(f"Failed to connect to email: {email_address}")
                return False
        except Exception as e:
            logger.error(f"Error adding email config: {e}")
            return False
    
    def remove_email_config(self, email_address: str):
        """Xóa cấu hình email"""
        if email_address in self._readers:
            self._readers[email_address].disconnect()
            del self._readers[email_address]
        if email_address in self._config:
            del self._config[email_address]
    
    def get_all_configs(self) -> List[Dict[str, Any]]:
        """Lấy tất cả cấu hình (ẩn password)"""
        configs = []
        for email, config in self._config.items():
            configs.append({
                'email': config['email'],
                'imap_server': config['imap_server'],
                'imap_port': config['imap_port'],
                'bank_account': config.get('bank_account'),
                'enabled': config.get('enabled', True)
            })
        return configs
    
    async def check_all_emails(self) -> List[BankTransaction]:
        """Check tất cả email và trả về giao dịch mới"""
        all_transactions = []
        
        for email_address, reader in self._readers.items():
            config = self._config.get(email_address, {})
            if not config.get('enabled', True):
                continue
            
            try:
                transactions = reader.fetch_bank_emails(since_hours=1, mark_as_read=True)
                all_transactions.extend(transactions)
            except Exception as e:
                logger.error(f"Error checking email {email_address}: {e}")
        
        return all_transactions
    
    def start_background_checker(self, callback=None):
        """Bắt đầu background task để check email định kỳ"""
        self._is_running = True
        
        async def _checker():
            while self._is_running:
                try:
                    transactions = await self.check_all_emails()
                    if transactions and callback:
                        for tx in transactions:
                            await callback(tx)
                except Exception as e:
                    logger.error(f"Background checker error: {e}")
                
                await asyncio.sleep(self._check_interval)
        
        return _checker
    
    def stop_background_checker(self):
        """Dừng background checker"""
        self._is_running = False
        
        # Disconnect all readers
        for reader in self._readers.values():
            reader.disconnect()


# Global instance
email_reader_manager = EmailReaderManager()
