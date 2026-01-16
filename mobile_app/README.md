# 📱 Hướng dẫn đóng gói 7TY Agent App

## 🚀 Phương pháp 1: PWA Builder (Đơn giản nhất)

### Bước 1: Deploy ứng dụng lên server có HTTPS
```bash
# Đảm bảo app chạy trên domain có SSL
https://your-domain.com/static/index.html
```

### Bước 2: Sử dụng PWA Builder
1. Truy cập https://www.pwabuilder.com/
2. Nhập URL của ứng dụng
3. Chọn platform:
   - **Android**: Tải APK
   - **Windows**: Tải MSIX
   - **iOS**: Tải Xcode project
4. Download và cài đặt

---

## 📦 Phương pháp 2: Capacitor (Professional)

### Yêu cầu
- Node.js 16+
- Android Studio (cho Android)
- Xcode (cho iOS - chỉ trên macOS)

### Bước 1: Cài đặt dependencies
```bash
cd mobile_app
npm install
```

### Bước 2: Build web app
```bash
npm run build
```

### Bước 3: Thêm platform

**Android:**
```bash
npm run cap:add:android
npm run cap:sync
npm run cap:open:android
```

**iOS:**
```bash
npm run cap:add:ios
npm run cap:sync
npm run cap:open:ios
```

### Bước 4: Build APK (Android)
```bash
cd android
./gradlew assembleRelease
```
APK sẽ ở: `android/app/build/outputs/apk/release/app-release.apk`

### Bước 5: Build IPA (iOS)
Mở Xcode project và build từ đó.

---

## 🖥️ Phương pháp 3: Electron (Desktop App)

### Tạo desktop app cho Windows/Mac/Linux
```bash
cd mobile_app
npm install electron electron-builder --save-dev
npm run build:desktop
```

---

## 🔧 Cấu hình API URL

Chỉnh sửa file `capacitor.config.json`:
```json
{
  "server": {
    "url": "https://your-domain.com/static/index.html"
  }
}
```

Hoặc để chạy offline, build web app vào thư mục `www`:
```json
{
  "webDir": "www"
}
```

---

## 📝 Ký và Publish

### Google Play Store
1. Tạo keystore:
```bash
keytool -genkey -v -keystore my-release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias my-alias
```

2. Cấu hình signing trong `android/app/build.gradle`

3. Build AAB:
```bash
./gradlew bundleRelease
```

### Apple App Store
1. Đăng ký Apple Developer Account ($99/năm)
2. Tạo App ID và Provisioning Profile
3. Archive và Upload từ Xcode

---

## 🎨 Icons và Splash Screen

### Tạo icons
Sử dụng công cụ: https://www.pwabuilder.com/imageGenerator

Kích thước cần thiết:
- Android: 48, 72, 96, 144, 192, 512 px
- iOS: 20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024 px

### Splash Screen
Đặt trong `android/app/src/main/res/drawable/splash.png`

---

## 🔒 Bluetooth Printer

Để sử dụng Bluetooth printer trên native app:

```bash
npm install @nicepayments/nicepay-capacitor-plugin
```

Thêm permissions vào `AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.BLUETOOTH"/>
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN"/>
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT"/>
<uses-permission android:name="android.permission.BLUETOOTH_SCAN"/>
```

---

## 📞 Hỗ trợ

Liên hệ: support@7ty.vn
Website: https://7ty.vn
