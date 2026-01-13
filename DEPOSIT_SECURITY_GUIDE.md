# Hệ Thống Nạp Tiền Bảo Mật - Đại Lý 7TY

## Tổng Quan

Hệ thống nạp tiền bảo mật mới được thiết kế với nhiều lớp bảo vệ để đảm bảo an toàn cho giao dịch của đại lý.

## Tính Năng Bảo Mật

### 1. Xác Thực 2 Lớp (OTP)
- Mỗi yêu cầu nạp tiền đều yêu cầu xác minh OTP 6 số
- OTP có hiệu lực 5 phút
- Tối đa 3 lần nhập sai, sau đó yêu cầu bị hủy
- Có thể gửi lại OTP (tối đa 3 lần)

### 2. Giới Hạn Giao Dịch (Rate Limiting)
- **Số tiền tối thiểu**: 100.000đ
- **Số tiền tối đa**: 100.000.000đ mỗi lần
- **Giới hạn hàng ngày**: 500.000.000đ
- **Số lần nạp tối đa/ngày**: 10 lần
- **Số lần nạp tối đa/giờ**: 3 lần
- **Ngưỡng cần duyệt**: > 50.000.000đ cần Admin duyệt

### 3. Phát Hiện Rủi Ro (Risk Assessment)
Hệ thống tự động đánh giá điểm rủi ro (0-100) dựa trên:
- Số tiền giao dịch lớn
- Đại lý mới (< 7 ngày)
- Số lần nạp trong ngày cao
- IP thay đổi
- Thời gian giao dịch bất thường (0h-6h)

Giao dịch có điểm rủi ro >= 50 sẽ:
- Bị đánh dấu để review
- Yêu cầu Admin duyệt

### 4. Theo Dõi IP & Device
- Lưu IP address mỗi request
- Lưu User-Agent
- Phát hiện thay đổi IP bất thường

### 5. Audit Trail
- Mỗi giao dịch có log chi tiết
- Ghi lại mọi hành động: tạo, xác minh, duyệt, hủy
- Lưu thông tin người thực hiện, thời gian

### 6. Webhook Verification
- Xác minh signature từ Casso/SePay
- Kiểm tra duplicate transaction
- Auto-match với deposit request

## API Endpoints

### Đại Lý

```
POST /api/v1/deposit/create
- Tạo yêu cầu nạp tiền mới
- Body: { amount, method, bank_account_id, notes }
- Response: { request_code, otp_sent, bank_info, expires_at }

POST /api/v1/deposit/verify-otp
- Xác minh OTP
- Body: { request_code, otp_code }

POST /api/v1/deposit/resend-otp
- Gửi lại OTP
- Params: request_code

GET /api/v1/deposit/requests
- Xem danh sách yêu cầu nạp tiền
- Params: status, limit, offset

POST /api/v1/deposit/cancel
- Hủy yêu cầu nạp tiền
- Params: request_code
```

### Webhook

```
POST /api/v1/deposit/webhook/bank
- Nhận thông báo từ ngân hàng
- Auto-process deposit
```

## Flow Nạp Tiền

### 1. Nạp Qua Chuyển Khoản

```
Đại lý -> Tạo yêu cầu -> Nhận OTP -> Xác minh OTP
                                          |
                     <- Nhận thông tin ngân hàng
                                          |
       Chuyển khoản với nội dung theo hướng dẫn
                                          |
Webhook ngân hàng -> Hệ thống auto-match
                                          |
          (Nếu khớp) -> Auto cộng tiền
          (Nếu > 50M) -> Chờ Admin duyệt
```

### 2. Nạp Tiền Mặt

```
Đại lý -> Tạo yêu cầu -> Nhận OTP -> Xác minh OTP
                                          |
                      <- Yêu cầu đang chờ xử lý
                                          |
               Admin xác nhận đã nhận tiền mặt
                                          |
                    <- Cộng tiền cho đại lý
```

## Database Models

### DepositRequest
```python
- request_code: Mã yêu cầu unique
- agent_id: Đại lý
- amount: Số tiền yêu cầu
- actual_amount: Số tiền thực tế nhận được
- method: bank_transfer, cash, bank_webhook
- status: pending, verified, approved, processing, completed, rejected, cancelled, expired
- verification_code: OTP
- verification_expires_at: Thời hạn OTP
- verification_attempts: Số lần đã thử
- is_verified: Đã xác minh OTP
- bank_reference: Mã giao dịch ngân hàng
- transfer_content: Nội dung chuyển khoản
- request_ip: IP tạo yêu cầu
- webhook_verified: Webhook đã xác minh
- previous_balance, new_balance: Số dư trước/sau
- audit_log: Log JSON chi tiết
```

### DepositLimit
```python
- agent_id: Áp dụng cho đại lý cụ thể (null = mặc định)
- min_amount, max_amount: Giới hạn số tiền
- daily_limit, monthly_limit: Giới hạn tổng
- max_daily_count, max_hourly_count: Giới hạn số lần
- require_otp: Yêu cầu OTP
- require_admin_approval: Luôn cần duyệt
- approval_threshold: Ngưỡng cần duyệt
```

### DepositSecurityLog
```python
- deposit_request_id: Liên kết yêu cầu
- agent_id: Đại lý
- event_type: Loại sự kiện
- event_description: Mô tả
- ip_address, user_agent: Thông tin client
- risk_score: Điểm rủi ro 0-100
- risk_factors: Các yếu tố rủi ro
- is_flagged: Đánh dấu đáng ngờ
```

## Migration

Chạy migration để tạo bảng:
```bash
python migrate_deposit_security.py
```

## Cấu Hình

### Giới hạn mặc định (tự động tạo khi migration)
- min_amount: 100.000đ
- max_amount: 100.000.000đ
- daily_limit: 500.000.000đ
- monthly_limit: 5.000.000.000đ
- max_daily_count: 10
- max_hourly_count: 3
- require_otp: true
- approval_threshold: 50.000.000đ

### Điều chỉnh giới hạn
Admin có thể tạo giới hạn riêng cho từng đại lý bằng cách thêm record vào bảng `deposit_limits` với `agent_id` cụ thể.

## Webhook Integration

### Casso
```json
{
    "data": [{
        "amount": 1000000,
        "description": "NAP DL001 1000000",
        "id": "unique_ref"
    }]
}
```

### SePay
```json
{
    "transferType": "in",
    "transferAmount": 1000000,
    "content": "NAP DL001 1000000",
    "transactionId": "unique_ref"
}
```

## Security Checklist

- [x] OTP verification với timeout
- [x] Rate limiting (count + amount)
- [x] IP tracking
- [x] Risk scoring
- [x] Audit logging
- [x] Webhook signature (cần cấu hình secret)
- [x] Duplicate detection
- [x] Auto-expiration

## Changelog

### v1.0.0 (2025-01-XX)
- Tạo hệ thống nạp tiền bảo mật mới
- Thêm OTP verification
- Thêm rate limiting
- Thêm risk assessment
- Thêm webhook auto-deposit
- Thêm audit trail đầy đủ
