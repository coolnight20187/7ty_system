# 🚀 HƯỚNG DẪN DEPLOY 7TY.VN LÊN CÁC NỀN TẢNG MIỄN PHÍ

## 📊 SO SÁNH CÁC NỀN TẢNG

| Nền tảng | Free Tier | Database | Region | Uptime | Đề xuất |
|----------|-----------|----------|--------|--------|---------|
| **Railway** | $5/tháng credit | PostgreSQL ✅ | Nhiều | 24/7 | ⭐⭐⭐⭐⭐ |
| **Render** | 750h/tháng | PostgreSQL (90 ngày) | Oregon/Frankfurt | Sleep sau 15' | ⭐⭐⭐⭐ |
| **Fly.io** | 3 VMs miễn phí | PostgreSQL ✅ | Singapore | 24/7 | ⭐⭐⭐⭐ |
| **Koyeb** | 2 nano instances | External only | Frankfurt | 24/7 | ⭐⭐⭐ |
| **Hugging Face** | Unlimited | SQLite only | US | 24/7 | ⭐⭐⭐ |

---

## 🥇 OPTION 1: RAILWAY (ĐỀ XUẤT NHẤT)

### Ưu điểm:
- ✅ $5 credit miễn phí mỗi tháng
- ✅ PostgreSQL miễn phí (trong credit)
- ✅ Deploy từ GitHub tự động
- ✅ Không sleep, chạy 24/7
- ✅ Hỗ trợ custom domain

### Bước triển khai:

#### 1. Đăng ký và kết nối GitHub
```
1. Truy cập: https://railway.app
2. Click "Login" -> "Login with GitHub"
3. Authorize Railway
```

#### 2. Tạo Project mới
```
1. Click "New Project"
2. Chọn "Deploy from GitHub repo"
3. Tìm và chọn repo "7ty_system"
4. Railway sẽ tự động detect Dockerfile
```

#### 3. Thêm PostgreSQL Database
```
1. Trong project, click "+ New"
2. Chọn "Database" -> "Add PostgreSQL"
3. Đợi database khởi tạo (1-2 phút)
```

#### 4. Cấu hình Environment Variables
Click vào service web -> Variables -> Add:

```env
DATABASE_TYPE=postgres
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
DB_NAME=${{Postgres.PGDATABASE}}
SECRET_KEY=your-super-secret-key-change-this-123456789
DEBUG=false
```

#### 5. Deploy
```
1. Railway tự động deploy khi có thay đổi
2. Xem logs trong tab "Deployments"
3. Lấy URL từ Settings -> Domains
```

#### 6. Custom Domain (Optional)
```
1. Settings -> Domains
2. Click "Generate Domain" hoặc thêm custom domain
3. Cấu hình DNS nếu dùng custom domain
```

---

## 🥈 OPTION 2: RENDER

### Ưu điểm:
- ✅ Đơn giản, dễ sử dụng
- ✅ Free PostgreSQL (90 ngày đầu)
- ✅ Auto-deploy từ GitHub
- ⚠️ Nhược: Sleep sau 15 phút không hoạt động

### Bước triển khai:

#### Cách 1: Sử dụng Blueprint (Tự động)
```
1. Truy cập: https://render.com
2. New -> Blueprint
3. Connect GitHub repo có file render.yaml
4. Review và Deploy
```

#### Cách 2: Deploy thủ công

##### Bước 1: Tạo PostgreSQL
```
1. New -> PostgreSQL
2. Name: 7ty-postgres
3. Database: 7ty_vn_db
4. User: 7ty_admin
5. Plan: Free
6. Create Database
```

##### Bước 2: Tạo Web Service
```
1. New -> Web Service
2. Connect GitHub repo
3. Settings:
   - Name: 7ty
   - Environment: Python 3
   - Build Command: pip install -r requirements.txt
   - Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   - Plan: Free
```

##### Bước 3: Environment Variables
```env
DATABASE_TYPE=postgres
DB_HOST=<từ PostgreSQL dashboard>
DB_PORT=5432
DB_USER=7ty_admin
DB_PASSWORD=<từ PostgreSQL dashboard>
DB_NAME=7ty_vn_db
SECRET_KEY=your-super-secret-key
```

---

## 🥉 OPTION 3: FLY.IO

### Ưu điểm:
- ✅ 3 shared VMs miễn phí
- ✅ PostgreSQL miễn phí (3GB)
- ✅ Có region Singapore (gần VN)
- ✅ Không sleep

### Bước triển khai:

#### 1. Cài đặt flyctl
```bash
# Linux/Mac
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

#### 2. Đăng nhập
```bash
fly auth login
```

#### 3. Launch App
```bash
cd /path/to/7ty_system
fly launch
# Chọn: Singapore (sin) region
# Chọn: No để tạo database sau
```

#### 4. Tạo PostgreSQL
```bash
fly postgres create --name 7ty-postgres --region sin
fly postgres attach 7ty-postgres --app 7ty
```

#### 5. Set Secrets
```bash
fly secrets set SECRET_KEY="your-super-secret-key-123"
fly secrets set DATABASE_TYPE="postgres"
fly secrets set DEBUG="false"
```

#### 6. Deploy
```bash
fly deploy
```

#### 7. Kiểm tra
```bash
fly status
fly logs
```

---

## 🔧 CẤU HÌNH BỔ SUNG

### Tạo Admin Account sau deploy
Truy cập terminal của app và chạy:
```bash
python init_admin.py
# Hoặc
python create_admin.py
```

### Kiểm tra Health
```
https://your-app-url/health
https://your-app-url/docs  # Swagger UI
```

---

## 🔐 BIẾN MÔI TRƯỜNG QUAN TRỌNG

| Biến | Mô tả | Bắt buộc |
|------|-------|----------|
| `DATABASE_TYPE` | `postgres` hoặc `sqlite` | ✅ |
| `DB_HOST` | Host của PostgreSQL | ✅ (nếu postgres) |
| `DB_PORT` | Port (thường 5432) | ✅ (nếu postgres) |
| `DB_USER` | Username | ✅ (nếu postgres) |
| `DB_PASSWORD` | Password | ✅ (nếu postgres) |
| `DB_NAME` | Tên database | ✅ (nếu postgres) |
| `SECRET_KEY` | JWT secret (32+ ký tự) | ✅ |
| `DEBUG` | `true` hoặc `false` | ❌ |
| `CORS_ORIGINS` | Allowed origins | ❌ |

---

## 📱 SAU KHI DEPLOY

### 1. Kiểm tra API
```bash
curl https://your-app.railway.app/health
```

### 2. Truy cập Admin Dashboard
```
https://your-app.railway.app/
```

### 3. Đăng nhập mặc định
```
Username: admin
Password: Admin@123
```

### 4. Cập nhật APK cho Mobile App
Sau khi deploy, cập nhật URL trong mobile app:
```javascript
const API_URL = "https://your-app.railway.app/api";
```

---

## ⚠️ LƯU Ý QUAN TRỌNG

1. **Đổi SECRET_KEY**: Luôn tạo key mạnh cho production
2. **Đổi mật khẩu admin**: Ngay sau lần đăng nhập đầu tiên
3. **Backup database**: Định kỳ backup dữ liệu
4. **Monitor usage**: Theo dõi credit/quota còn lại
5. **HTTPS**: Các platform đều hỗ trợ HTTPS miễn phí

---

## 🆘 TROUBLESHOOTING

### App không start
```bash
# Kiểm tra logs
fly logs  # Fly.io
# Hoặc xem logs trong dashboard của Railway/Render
```

### Database connection failed
1. Kiểm tra environment variables
2. Đảm bảo database đã được tạo và attach

### Import error
```bash
# Đảm bảo requirements.txt đầy đủ
pip freeze > requirements.txt
```

---

## 📞 SUPPORT

Nếu gặp vấn đề:
1. Xem logs của platform
2. Kiểm tra /health endpoint
3. Verify environment variables
4. Check database connection
