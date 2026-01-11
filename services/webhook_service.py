import requests
import json
import hashlib
import hmac
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self):
        self.webhook_urls = {
            'payment_success': None,
            'payment_failed': None,
            'agent_registered': None,
            'bill_created': None,
            'bill_paid': None,
            'system_alert': None
        }
    
    def send_webhook(self, event_type: str, data: Dict[str, Any], url: Optional[str] = None) -> bool:
        """
        Gửi webhook
        
        Args:
            event_type: Loại sự kiện
            data: Dữ liệu gửi kèm
            url: URL webhook (nếu None sẽ dùng URL mặc định)
        
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            # Lấy URL webhook
            webhook_url = url or self.webhook_urls.get(event_type)
            
            if not webhook_url:
                logger.warning(f"No webhook URL configured for event: {event_type}")
                return False
            
            # Chuẩn bị payload
            payload = {
                'event': event_type,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            
            # Tạo signature
            signature = self._generate_signature(payload)
            
            # Gửi request
            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Signature': signature,
                'X-Webhook-Event': event_type,
                'User-Agent': '7TY.VN Webhook Service'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Webhook sent successfully: {event_type}")
                return True
            else:
                logger.error(f"Webhook failed: {event_type} - Status: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook request error: {event_type} - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Webhook error: {event_type} - {str(e)}")
            return False
    
    def _generate_signature(self, payload: Dict[str, Any]) -> str:
        """
        Tạo chữ ký cho webhook
        
        Args:
            payload: Dữ liệu payload
        
        Returns:
            str: Chữ ký
        """
        secret = Config.SECRET_KEY.encode()
        message = json.dumps(payload, sort_keys=True).encode()
        
        signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return signature
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Xác thực chữ ký webhook
        
        Args:
            payload: Dữ liệu payload (bytes)
            signature: Chữ ký nhận được
        
        Returns:
            bool: True nếu chữ ký hợp lệ
        """
        try:
            secret = Config.SECRET_KEY.encode()
            expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
            return False
    
    def send_payment_success_webhook(self, transaction_data: Dict[str, Any]) -> bool:
        """
        Gửi webhook khi thanh toán thành công
        
        Args:
            transaction_data: Dữ liệu giao dịch
        
        Returns:
            bool: True nếu gửi thành công
        """
        payload = {
            'transaction_id': transaction_data.get('id'),
            'transaction_code': transaction_data.get('transaction_code'),
            'amount': transaction_data.get('amount'),
            'status': 'completed',
            'payment_method': transaction_data.get('payment_method'),
            'timestamp': datetime.now().isoformat()
        }
        
        return self.send_webhook('payment_success', payload)
    
    def send_agent_registered_webhook(self, agent_data: Dict[str, Any]) -> bool:
        """
        Gửi webhook khi đại lý đăng ký
        
        Args:
            agent_data: Dữ liệu đại lý
        
        Returns:
            bool: True nếu gửi thành công
        """
        payload = {
            'agent_id': agent_data.get('id'),
            'agent_code': agent_data.get('agent_code'),
            'company_name': agent_data.get('company_name'),
            'owner_name': agent_data.get('owner_name'),
            'status': agent_data.get('status'),
            'registered_at': datetime.now().isoformat()
        }
        
        return self.send_webhook('agent_registered', payload)
    
    def send_bill_paid_webhook(self, bill_data: Dict[str, Any]) -> bool:
        """
        Gửi webhook khi hóa đơn được thanh toán
        
        Args:
            bill_data: Dữ liệu hóa đơn
        
        Returns:
            bool: True nếu gửi thành công
        """
        payload = {
            'bill_id': bill_data.get('id'),
            'bill_code': bill_data.get('bill_code'),
            'customer_code': bill_data.get('customer_code'),
            'amount': bill_data.get('final_amount'),
            'paid_at': datetime.now().isoformat(),
            'payment_method': bill_data.get('payment_method')
        }
        
        return self.send_webhook('bill_paid', payload)
    
    def send_system_alert_webhook(self, alert_type: str, message: str, severity: str = 'warning') -> bool:
        """
        Gửi webhook cảnh báo hệ thống
        
        Args:
            alert_type: Loại cảnh báo
            message: Nội dung cảnh báo
            severity: Mức độ nghiêm trọng (info, warning, error, critical)
        
        Returns:
            bool: True nếu gửi thành công
        """
        payload = {
            'alert_type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'system_version': Config.SYSTEM_VERSION
        }
        
        return self.send_webhook('system_alert', payload)
    
    def set_webhook_url(self, event_type: str, url: str):
        """
        Cấu hình URL webhook
        
        Args:
            event_type: Loại sự kiện
            url: URL webhook
        """
        if event_type in self.webhook_urls:
            self.webhook_urls[event_type] = url
            logger.info(f"Webhook URL set for {event_type}: {url}")
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def test_webhook(self, event_type: str, url: str) -> Dict[str, Any]:
        """
        Kiểm tra webhook
        
        Args:
            event_type: Loại sự kiện
            url: URL webhook
        
        Returns:
            Dict: Kết quả kiểm tra
        """
        test_data = {
            'test': True,
            'event': event_type,
            'timestamp': datetime.now().isoformat(),
            'message': 'Test webhook from 7TY.VN system'
        }
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': '7TY.VN Webhook Test'
            }
            
            response = requests.post(
                url,
                json=test_data,
                headers=headers,
                timeout=10
            )
            
            result = {
                'success': response.status_code in [200, 201, 202],
                'status_code': response.status_code,
                'response_text': response.text,
                'response_time': response.elapsed.total_seconds()
            }
            
            logger.info(f"Webhook test result: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            error_result = {
                'success': False,
                'error': str(e),
                'status_code': None
            }
            logger.error(f"Webhook test failed: {error_result}")
            return error_result

async def send_webhook_notification(
    event_type: str,
    data: Dict[str, Any],
    url: Optional[str] = None
) -> bool:
    """
    Gửi thông báo webhook (async version)
    """
    try:
        return webhook_service.send_webhook(event_type, data, url)
    except Exception as e:
        logger.error(f"Failed to send webhook notification: {e}")
        return False

# Tạo instance global
webhook_service = WebhookService()