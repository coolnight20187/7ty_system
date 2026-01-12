# 7TY Bank Notification Reader - Build Guide

## Tổng quan

App đọc thông báo (notification) từ app ngân hàng ACB để tự động nạp tiền cho đại lý.

### Các thành phần

1. **BankNotificationService.java** - NotificationListenerService đọc thông báo ngân hàng
2. **NotificationReaderPlugin.java** - Capacitor Plugin để UI giao tiếp với service
3. **www/index.html** - Giao diện chính với tabs SMS/Notification
4. **www/notification_reader.html** - Trang riêng cho Notification Reader (optional)

## Cách hoạt động

1. App đọc thông báo push từ app ACB khi có giao dịch mới
2. Parse nội dung: số tiền, nội dung chuyển khoản, số tài khoản
3. Gửi lên server `/api/v1/bank-webhook`
4. Server tìm mã đại lý trong nội dung (VD: NAP 7TY001)
5. Tự động cộng tiền vào ví đại lý

## Ngân hàng được hỗ trợ

| Ngân hàng | Package Name | Mã |
|-----------|--------------|-----|
| ACB | com.acb.acbmobile, vn.com.acb.acbmobile | ACB |
| MB Bank | com.mbmobile, vn.com.mbbank.mb | MB |
| Vietcombank | com.VCB | VCB |
| Techcombank | vn.com.techcombank.bb.app | TCB |
| VPBank | com.vnpay.vpbankonline | VPB |
| TPBank | vn.tpb.mb.gprsandroid | TPB |
| BIDV | com.vnpay.bidv | BIDV |
| VietinBank | com.vietinbank.ipay | CTG |
| Sacombank | vn.stb.mbanking | STB |
| Agribank | com.vnpay.agribank | AGR |

## Build APK

### Yêu cầu
- Node.js 18+
- Android Studio
- JDK 17

### Bước build

```bash
# 1. Cài dependencies
cd sms_reader_app
npm install

# 2. Sync Capacitor
npx cap sync android

# 3. Build APK từ Android Studio
cd android
./gradlew assembleDebug

# APK nằm tại: android/app/build/outputs/apk/debug/app-debug.apk
```

### Build Release APK

```bash
cd android
./gradlew assembleRelease
```

## Cài đặt và sử dụng

### 1. Cài APK trên điện thoại

```bash
adb install app-debug.apk
```

### 2. Cấp quyền Notification Access

1. Mở app 7TY SMS Reader
2. Chọn tab "Notification" 
3. Nhấn "Mở Cài Đặt Notification Access"
4. Bật quyền cho "7TY SMS Reader" / "7TY Bank Notification Reader"

### 3. Cấu hình

1. Nhập Server URL: `https://sevenapp.onrender.com`
2. Nhấn "Lưu Cấu Hình"
3. Nhấn "Bắt Đầu"

### 4. Test

Chuyển khoản vào tài khoản ACB của hệ thống với nội dung theo format:
```
NAP {mã_đại_lý} {số_tiền}
```

Ví dụ:
```
NAP AG000001 1000000
NAP 7TY001 5000000
```

Số tiền sẽ tự động được cộng vào ví đại lý tương ứng.

## Format Nội Dung Chuyển Khoản

Format chuẩn (đồng bộ với app Đại lý):
```
NAP {agent_code} {amount}
```

Các format được hỗ trợ:
| Format | Ví dụ | Mô tả |
|--------|-------|-------|
| NAP + mã + số tiền | NAP AG000001 1000000 | Format chuẩn từ app |
| NAP + mã | NAP 7TY001 | Không có số tiền |
| NAPTIEN + mã | NAPTIEN DL001 | Dùng NAPTIEN |
| mã + NAP | 7TY001 NAP | Mã trước từ khóa |

## Troubleshooting

### Service không chạy sau khi reboot
- Vào lại Notification Access settings và bật lại quyền

### Không đọc được thông báo ACB
- Đảm bảo app ACB có quyền hiển thị thông báo
- Kiểm tra ACB có cài đặt nhận thông báo giao dịch

### Server không nhận được request
- Kiểm tra URL server đúng
- Kiểm tra kết nối internet

## API Webhook Format

```json
{
  "type": "credit",
  "amount": 100000,
  "content": "NAP 7TY001",
  "reference": "NOTIF_1234567890",
  "bank_code": "ACB",
  "account_number": "123456789",
  "source": "notification_reader"
}
```

## Version History

- **v2.0.0** - Thêm Notification Reader cho ACB
- **v1.0.0** - SMS Reader ban đầu
