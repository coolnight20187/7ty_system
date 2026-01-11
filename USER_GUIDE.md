# 🎯 HƯỚNG DẪN SỬ DỤNG - 7TY.VN SYSTEM v4.0.0

## 🔑 ĐĂNG NHẬP

### URL: `http://localhost:8000/login`

**Tài khoản Admin Mặc Định:**
- Username: `admin`
- Password: `Admin@123`

**Sau khi đăng nhập:**
1. JWT token được lưu trong localStorage
2. Tự động chuyển hướng tới Dashboard
3. Có thể truy cập tất cả các module theo quyền hạn

---

## 📊 DASHBOARD (Trang Chủ)

**URL**: `http://localhost:8000`

### Thông Tin Hiển Thị:
- 📈 Tổng số Đại Lý
- 📄 Hóa Đơn Đã Xử Lý
- 💰 Doanh Thu Hôm Nay
- 🔄 Giao Dịch Hôm Nay
- 📊 Biểu đồ xu hướng (trending)
- 📋 Hoạt động gần đây (latest activities)
- 🏆 Top đại lý (highest revenue)

### Hành Động:
- Nhấp vào bất kỳ thẻ thống kê nào để xem chi tiết
- Xem hoạt động theo thời gian thực
- Quay lại dashboard từ bất kỳ trang nào

---

## 👥 QUẢN LÝ ĐẠI LÝ (Agents)

**Menu**: Sidebar → "Quản lý Đại lý"  
**URL**: `http://localhost:8000` → Click menu

### ✨ Tính Năng Chính:

#### 1️⃣ **Danh Sách Đại Lý** (Tab 1)
```
Hiển thị: Mã, Tên, Chủ sở hữu, Điện thoại, Địa chỉ, Ngày đăng ký
Hành động: Xem chi tiết, Chỉnh sửa
```
- Tìm kiếm: Gõ tên hoặc mã đại lý
- Sắp xếp: Click vào header cột
- Phân trang: Điều hướng bằng các nút trang

#### 2️⃣ **Đợi Phê Duyệt** (Tab 2)
```
Yêu cầu mới được gửi từ:
- Nhân viên tạo đại lý mới
- Nạp tiền vào ví đại lý
- Khách thẻ đăng ký
```
**Hành động**:
- ✅ Xác nhận phê duyệt (cộng số dư vào ví)
- ✏️ Sửa thông tin
- ❌ Hủy yêu cầu (từ chối)

#### 3️⃣ **Lịch Sử** (Tab 3)
```
Tất cả giao dịch đại lý
- Nạp tiền lịch sử
- Rút tiền lịch sử
- Các thay đổi thông tin
```
**Xuất Excel**: Click nút "Lịch Sử" → Download

### 📝 Thêm Đại Lý Mới:

1. Click "Thêm Đại Lý"
2. Điền form:
   - Tên Đại Lý
   - Tên Chủ Đại Lý
   - Số điện thoại
   - Địa chỉ
   - Loại (Cá nhân / Công ty)
   - Upload giấy phép (nếu có)
3. Submit → Chờ phê duyệt từ admin

---

## 📄 QUẢN LÝ HÓA ĐƠN ĐIỆN (Bills)

**Menu**: Sidebar → "Hóa đơn Điện"  
**Chức năng**: Quản lý kho hóa đơn điện

### ✨ Tính Năng Chính:

#### 1️⃣ **Kho Hóa Đơn** (Tab 1)
```
Hóa đơn chưa bán trong kho
Hiển thị: Mã KH, Tên, Kỳ, Tiền, Ngân Hàng, Trạng Thái
Hành động: Xem, Chỉnh sửa, Xóa
```

**Tìm kiếm**:
- Mã hoặc tên khách hàng
- Lọc mệnh giá (VD: 100K - 500K)
- Lọc theo ngân hàng
- Lọc theo trạng thái

**Sao chép**:
- Chọn hóa đơn (checkbox)
- Click "Sao chép"
- Dán vào Excel/Word

#### 2️⃣ **Tra Cứu Hóa Đơn** (Tab 2) - 🌟 ADVANCED FEATURE

```
Công cụ tìm kiếm hóa đơn hàng loạt
```

**Cách sử dụng**:
1. Nhập tên hoặc ID khách thẻ
   - Autocomplete sẽ gợi ý
   - Hiển thị: Tên - ID - Ngân Hàng
2. Chọn từ gợi ý hoặc nhấn tìm
3. Xem kết quả (danh sách hóa đơn)

**Hành động**:
- ✅ Sao chép kết quả
- ⬇️ Xuất Excel
- 👁️ Xem chi tiết
- 🗑️ Xóa khỏi kho

**Lọc bổ sung**:
- Mệnh giá: Từ → Đến
- Kỳ thanh toán
- Trạng thái
- Ngân hàng

#### 3️⃣ **Lịch Sử** (Tab 3)
```
Tất cả hóa đơn đã bán
- Người bán (Đại lý / Nhân viên)
- Khách mua (Khách thẻ)
- Ngày bán
- Trạng thái thanh toán
```

**Xuất Excel**: Click "Lịch Sử" → Download

### 🚀 Nhập Hóa Đơn Mới:

1. Click "Nhập Hóa Đơn"
2. Chọn nguồn:
   - Upload CSV/Excel
   - Nhập thủ công
3. Điền/kiểm tra thông tin:
   - Mã KH, Tên KH
   - Kỳ thanh toán
   - Tiền trước, tiền này, tổng
   - Ngân Hàng
4. Submit → Hóa đơn vào kho

---

## 💳 QUẢN LÝ KHÁCH THẺ (Cardholders)

**Menu**: Sidebar → "Khách thẻ"  
**Chức năng**: Quản lý khách hàng thẻ tín dụng

### ✨ Tính Năng Chính:

#### 1️⃣ **Danh Sách Khách Thẻ** (Tab 1)
```
Tất cả khách thẻ
Hiển thị: Tên, ID (SĐT), Số Thẻ, Ngân Hàng, Hạn Thanh Toán, Nợ Hiện Tại
Hành động: Xem, Sửa, Xóa, Phê Duyệt
```

**Tìm kiếm**:
- Tên khách
- Số điện thoại
- Lọc theo ngân hàng

**Sắp xếp**:
- Theo nợ cao nhất
- Theo deadline gần nhất
- Theo tên alphabetically

#### 2️⃣ **Quản Lý Thẻ** (Tab 2)
```
Danh sách tất cả thẻ tín dụng
Hiển thị: Tên Khách, Số Thẻ, Ngân Hàng, Hạn Mức, Miễn Lãi
Hành động: Xem, Chỉnh sửa, Xóa
```

**Thêm Thẻ**:
1. Click "Thêm Thẻ"
2. Chọn Khách Thẻ (autocomplete)
3. Điền thông tin:
   - Số Thẻ (16 chữ số)
   - Ngày hết hạn (MM/YY)
   - CVV (3 chữ số)
   - Ngân Hàng
   - Dòng Thẻ (Classic/Premium/Platinum)
   - Ngày Chốt Sao Kê (1-31)
   - Miễn Lãi (45/55 ngày)
   - Hạn Mức (giới hạn nợ)
   - Ưu đãi (% cashback/rewards)
4. Submit

#### 3️⃣ **Thẻ Sắp Hết Hạn** (Tab 3)
```
Thẻ còn 5 ngày tới deadline thanh toán
Cần thu tiền gấp
Hiển thị: Tên Khách, Số Thẻ, Hạn Thanh Toán, Nợ
Hành động: Xử lý thanh toán
```

#### 4️⃣ **Phê Duyệt** (Tab 4)
```
Yêu cầu mới:
- Khách thẻ mới đăng ký
- Yêu cầu rút tiền
```

**Hành động**:
- ✅ Xác nhận phê duyệt
- 📝 Xem chi tiết yêu cầu
- ❌ Từ chối yêu cầu

### 📝 Thêm Khách Thẻ:

1. Click "Thêm Khách Thẻ"
2. Điền form:
   - **Tài Khoản**: Username, Email, Password
   - **Cá Nhân**: Họ tên, SĐT, CMND/CCCD, Ngày sinh
   - **Pháp Nhân**: Tên công ty, Mã số thuế, Địa chỉ
   - **Hình Ảnh**: Upload avatar/giấy CMND
3. Submit → Chờ phê duyệt

### 💰 Tra Cứu Nợ Thẻ:

**Thời hạn thanh toán được tính**:
- Ngày chốt sao kê: Ngày cố định hàng tháng
- Hạn thanh toán = Ngày chốt + (15 hoặc 25 ngày)
  - +15 ngày nếu Miễn Lãi 45 ngày
  - +25 ngày nếu Miễn Lãi 55 ngày

**Trạng Thái**:
- 📋 "Đã có Sao Kê": Đã qua ngày chốt
- ⏰ "Sát Hạn": Còn 5 ngày tới deadline
- ✅ "Đáo Xong - DD/MM": Đã thanh toán

---

## 👔 QUẢN LÝ NHÂN VIÊN (Staff)

**Menu**: Sidebar → "Nhân viên"  
**Chức năng**: Quản lý tài khoản nhân viên

### ✨ Tính Năng Chính:

#### 📋 **Danh Sách Nhân Viên**
```
Tất cả nhân viên
Hiển thị: Tên, ID (SĐT), Email, Chức Vụ, Quyền Hạn, Trạng Thái, Ngày Tham Gia
Hành động: Sửa, Xóa
```

**Tìm kiếm**:
- Tên nhân viên
- Email
- Số điện thoại

**Lọc**:
- Theo chức vụ
- Theo quyền hạn (Admin/Manager/Staff/Viewer)
- Theo trạng thái (Active/Inactive)

### 👤 Thêm Nhân Viên:

1. Click "Thêm Nhân Viên"
2. Điền form:
   - **Tài Khoản**: Username, Email, Password
   - **Cá Nhân**: Họ tên, SĐT, CMND, Ngày sinh
   - **Công Việc**: Chức vụ, Bộ phận
   - **Quyền**: Role (Admin/Manager/Staff/Viewer)
   - **Trạng Thái**: Active/Inactive
   - **Hình Ảnh**: Avatar
3. Submit → Nhân viên có thể đăng nhập

### 🔐 Quản Lý Quyền Hạn:

**Admin** (Quản Trị Viên)
- Toàn quyền hệ thống
- Quản lý người dùng, cấu hình
- Phê duyệt tất cả

**Manager** (Trình Quản Lý)
- Quản lý dữ liệu
- Phê duyệt giao dịch
- Không được thay đổi cấu hình

**Staff** (Nhân Viên)
- Nhập liệu
- Xem report
- Không phê duyệt

**Viewer** (Người Xem)
- Chỉ xem dữ liệu
- Không chỉnh sửa
- Không phê duyệt

---

## ⚙️ CÀI ĐẶT (Settings)

**Menu**: Sidebar → "Cài đặt"

### 1️⃣ **Cài Đặt Hệ Thống**
- Tên công ty
- Email liên hệ
- Số điện thoại
- Thời giờ làm việc
- Ngày nghỉ

### 2️⃣ **API & Webhooks**
```
API Key: sk_xxxxxxxxxxxx
API URL: http://localhost:8000/api
```

**Sử dụng API**:
```bash
# Get agent list
curl -X GET "http://localhost:8000/api/agents" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create bill
curl -X POST "http://localhost:8000/api/bills" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_code":"KH001","total_amount":500000}'
```

### 3️⃣ **Bảo Mật**
- Đổi mật khẩu
- 2FA (Two-Factor Authentication)
- Quản lý session
- API key rotation

### 4️⃣ **Sao Lưu & Khôi Phục**
- Sao lưu cơ sở dữ liệu
- Lên lịch auto-backup
- Khôi phục từ bản sao lưu
- Export dữ liệu

---

## 💡 MẸO & HƯỚNG DẪN

### ⚡ Tìm Kiếm Nhanh
- Dùng global search (header): Tìm nhanh bất cứ đối tượng nào
- Các gợi ý hiển thị trong khi gõ

### 📊 Xuất Dữ Liệu
- Excel: Chọn dòng → Export
- PDF: Print → Save as PDF
- CSV: Export → Mở bằng Excel

### 🔔 Thông Báo
- Badge notification (chuông)
- Email khi phê duyệt
- SMS alert (future feature)

### 📱 Mobile Access
- Responsive design
- Giao diện tối ưu cho mobile
- Sidebar collapse trên điện thoại

### 🌙 Dark Mode
- Click icon moon (header)
- Tự động lưu preference

---

## ❓ NHỮNG CÂU HỎI THƯỜNG GẶP

**Q: Làm sao lấy lại password?**  
A: Click "Quên mật khẩu" → Nhập email → Kiểm tra email → Reset link

**Q: Phê duyệt Đại Lý là gì?**  
A: Admin phải xác nhận Đại Lý mới mới có thể đăng nhập và sử dụng

**Q: Làm sao bán hóa đơn cho Khách Thẻ?**  
A: Tab Tra Cứu → Tìm khách → Chọn hóa đơn → Click "Bán" → Xác nhận

**Q: Hạn thanh toán thẻ được tính như thế nào?**  
A: Ngày chốt + 15 ngày (45 days free) hoặc +25 ngày (55 days free)

**Q: Có thể export dữ liệu không?**  
A: Có, mỗi trang có nút "Xuất Excel"

**Q: Như thế nào để tặng quyền Admin cho nhân viên?**  
A: Sửa nhân viên → Thay đổi Role → "Admin" → Save

---

## 🆘 LỖI THƯỜNG GẶP & GIẢI PHÁP

| Lỗi | Nguyên Nhân | Giải Pháp |
|-----|-----------|----------|
| Không thể đăng nhập | Tài khoản/mật khẩu sai | Check caps lock, xác nhận thông tin |
| Không tải dữ liệu | Kết nối API lỗi | Refresh trang, kiểm tra internet |
| Timeout | Server bận | Đợi vài phút, thử lại |
| Token hết hạn | Session quá lâu | Đăng xuất → Đăng nhập lại |
| Xuất Excel không được | Permission lỗi | Kiểm tra quyền hạn, liên hệ admin |

---

## 📞 LIÊN HỆ HỖ TRỢ

**Email**: admin@7ty.vn  
**Hotline**: +84 (xxx) xxx-xxxx  
**Support Hours**: 8:00 AM - 6:00 PM (Mon-Fri)  
**Website**: https://7ty.vn

---

**Version**: 4.0.0 Professional  
**Last Updated**: 2025-12-25  
**Status**: ✅ Ready for Use
