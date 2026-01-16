#!/bin/bash

# =====================================================
# SCRIPT ĐÓNG GÓI APK TỰ ĐỘNG
# Tránh lỗi quên cập nhật file hoặc phiên bản
# =====================================================

set -e  # Dừng nếu có lỗi

# Màu sắc
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Thư mục gốc
ROOT_DIR="/workspaces/7ty_system"
MOBILE_DIR="$ROOT_DIR/mobile_app"
WWW_DIR="$MOBILE_DIR/www"
ANDROID_DIR="$MOBILE_DIR/android"
DOWNLOADS_DIR="$ROOT_DIR/static/downloads"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   SCRIPT ĐÓNG GÓI APK TỰ ĐỘNG${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# =====================================================
# BƯỚC 1: Kiểm tra phiên bản trong index.html
# =====================================================
echo -e "${YELLOW}[BƯỚC 1] Kiểm tra phiên bản hiện tại...${NC}"

CURRENT_VERSION=$(grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" "$WWW_DIR/index.html" | head -1)
echo "Phiên bản hiện tại: $CURRENT_VERSION"

# Hỏi người dùng có muốn thay đổi phiên bản không
read -p "Nhập phiên bản mới (Enter để giữ $CURRENT_VERSION): " NEW_VERSION
if [ -z "$NEW_VERSION" ]; then
    NEW_VERSION=$CURRENT_VERSION
fi

echo "Sử dụng phiên bản: $NEW_VERSION"

# =====================================================
# BƯỚC 2: Cập nhật phiên bản trong TẤT CẢ các file
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 2] Cập nhật phiên bản trong tất cả file...${NC}"

# Cập nhật index.html
if [ "$NEW_VERSION" != "$CURRENT_VERSION" ]; then
    sed -i "s/$CURRENT_VERSION/$NEW_VERSION/g" "$WWW_DIR/index.html"
    echo "✅ Đã cập nhật index.html"
    
    # Cập nhật sms_reader.html
    sed -i "s/$CURRENT_VERSION/$NEW_VERSION/g" "$WWW_DIR/sms_reader.html"
    echo "✅ Đã cập nhật sms_reader.html"
    
    # Cập nhật build.gradle
    OLD_VERSION_NAME=$(echo $CURRENT_VERSION | sed 's/v//')
    NEW_VERSION_NAME=$(echo $NEW_VERSION | sed 's/v//')
    sed -i "s/versionName \"$OLD_VERSION_NAME\"/versionName \"$NEW_VERSION_NAME\"/g" "$ANDROID_DIR/app/build.gradle"
    
    # Tăng versionCode
    OLD_CODE=$(grep "versionCode" "$ANDROID_DIR/app/build.gradle" | head -1 | grep -oE "[0-9]+")
    NEW_CODE=$((OLD_CODE + 1))
    sed -i "s/versionCode $OLD_CODE/versionCode $NEW_CODE/g" "$ANDROID_DIR/app/build.gradle"
    echo "✅ Đã cập nhật build.gradle (versionCode: $NEW_CODE, versionName: $NEW_VERSION_NAME)"
fi

# =====================================================
# BƯỚC 3: QUAN TRỌNG - Không cần sync vì chỉ dùng index.html
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 3] Xác nhận index.html là file chính...${NC}"
echo "✅ Chỉ sử dụng index.html (không cần sync)"

# =====================================================
# BƯỚC 4: Sync Capacitor
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 4] Chạy npx cap sync android...${NC}"
cd "$MOBILE_DIR"
npx cap sync android

# =====================================================
# BƯỚC 5: Xác nhận sync
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 5] Xác nhận nội dung đã sync...${NC}"
SYNCED_VERSION=$(grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" "$ANDROID_DIR/app/src/main/assets/public/index.html" | head -1)
echo "Phiên bản trong assets/public/index.html: $SYNCED_VERSION"

if [ "$SYNCED_VERSION" != "$NEW_VERSION" ]; then
    echo -e "${RED}❌ LỖI: Phiên bản không khớp!${NC}"
    exit 1
fi
echo "✅ Sync thành công"

# =====================================================
# BƯỚC 6: Build APK
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 6] Build APK Release...${NC}"
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd "$ANDROID_DIR"
./gradlew clean assembleRelease

# =====================================================
# BƯỚC 7: Xác minh APK
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 7] Xác minh nội dung APK...${NC}"
APK_PATH="$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
TEMP_DIR="/tmp/apk_verify_$$"
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"
unzip -q "$APK_PATH"

APK_VERSION=$(grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" assets/public/index.html | head -1)
echo "Phiên bản trong APK: $APK_VERSION"

if [ "$APK_VERSION" != "$NEW_VERSION" ]; then
    echo -e "${RED}❌ LỖI: APK chứa phiên bản sai!${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi
echo "✅ APK đã xác minh"
rm -rf "$TEMP_DIR"

# =====================================================
# BƯỚC 8: Copy APK vào downloads
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 8] Copy APK vào thư mục downloads...${NC}"
VERSION_NAME=$(echo $NEW_VERSION | sed 's/v//')
TIMESTAMP=$(date +%H%M)
APK_FILENAME="7ty-agent-v${VERSION_NAME}.apk"

# Xóa APK cũ
rm -f "$DOWNLOADS_DIR"/agent-app-*.apk
rm -f "$DOWNLOADS_DIR"/7ty-agent-*.apk

# Copy APK mới
cp "$APK_PATH" "$DOWNLOADS_DIR/$APK_FILENAME"
echo "✅ Đã tạo: $APK_FILENAME"

# =====================================================
# BƯỚC 9: Cập nhật Docker container (nếu đang chạy)
# =====================================================
echo ""
echo -e "${YELLOW}[BƯỚC 9] Cập nhật Docker container...${NC}"
if docker ps | grep -q "7ty_app"; then
    docker exec 7ty_app rm -rf /app/static/downloads/*.apk 2>/dev/null || true
    docker cp "$DOWNLOADS_DIR/$APK_FILENAME" 7ty_app:/app/static/downloads/
    docker cp "$WWW_DIR/index.html" 7ty_app:/app/static/index.html
    docker cp "$WWW_DIR/index.html" 7ty_app:/app/static/index.html
    docker restart 7ty_app
    echo "✅ Container đã cập nhật"
else
    echo "⚠️ Container 7ty_app không chạy, bỏ qua"
fi

# =====================================================
# TỔNG KẾT
# =====================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   HOÀN TẤT ĐÓNG GÓI APK${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📦 Thông tin APK:"
echo "   - Phiên bản: $NEW_VERSION"
echo "   - File: $DOWNLOADS_DIR/$APK_FILENAME"
echo "   - Dung lượng: $(ls -lh "$DOWNLOADS_DIR/$APK_FILENAME" | awk '{print $5}')"
echo ""
echo "✅ Tất cả file đã được đồng bộ:"
echo "   - index.html"
echo "   - index.html"  
echo "   - sms_reader.html"
echo "   - build.gradle"
echo ""
