# 7TY.VN - Hệ Thống Quản Trị Đại Lý Thu Hộ

## 📋 Giới Thiệu

7TY.VN là một hệ thống quản lý đầy đủ cho các công ty/cá nhân cung cấp dịch vụ thu hộ điện. Hệ thống được xây dựng với FastAPI, SQLAlchemy, và hỗ trợ các tính năng:

- **Quản lý người dùng**: Tạo, cập nhật, xóa người dùng với các vai trò khác nhau
- **Quản lý đại lý**: Quản lý thông tin đại lý, hạn mức, hoa hồng
- **Quản lý hóa đơn**: Import, quản lý, thanh toán hóa đơn
- **Quản lý khách hàng**: Theo dõi thông tin khách hàng
- **Quản lý giao dịch**: Theo dõi tất cả các giao dịch
- **Dashboard & Báo cáo**: Thống kê, phân tích dữ liệu
- **API External**: Cung cấp API cho ứng dụng bên thứ ba

## 🚀 Cài Đặt & Chạy

### Yêu cầu
- Python 3.10+
- pip (Python package manager)
- Một terminal/command prompt

### Bước 1: Cài đặt Dependencies
```bash
pip install -r requirements.txt
```

### Bước 2: Khởi chạy Server
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8003
```

Hoặc dùng file `quick_start.py`:
```bash
python quick_start.py
```

### Bước 3: Truy cập Ứng Dụng
- **API Documentation (Swagger UI)**: http://127.0.0.1:8003/docs
- **Alternative Documentation (ReDoc)**: http://127.0.0.1:8003/redoc
- **Health Check**: http://127.0.0.1:8003/health

## 📁 Cấu Trúc Dự Án

```
7ty_system/
├── main.py                 # Entry point
├── config.py              # Configuration
├── database.py            # Database setup
├── models.py              # SQLAlchemy models
├── schemas.py             # Pydantic schemas
├── dependencies.py        # FastAPI dependencies
├── security.py            # Security utilities
├── utils.py               # Utility functions
├── routers/               # API route handlers
│   ├── auth.py
│   ├── users.py
│   ├── agents.py
│   ├── bills.py
│   ├── transactions.py
│   ├── customers.py
│   ├── api.py
│   ├── system.py
│   ├── reports.py
│   └── websocket.py
├── services/              # Business logic services
│   ├── email_service.py
│   ├── file_service.py
│   └── webhook_service.py
└── static/                # Static files & uploads
    └── uploads/
```

## 🔐 Tài Khoản Mặc Định

Admin user được tạo tự động lần đầu khởi động (nếu bật khởi tạo sample data):
- **Username**: admin
- **Password**: Admin@123
- **Email**: admin@7ty.vn

**Lưu ý**: Hãy đổi mật khẩu ngay sau khi đăng nhập lần đầu!

## 📚 API Endpoints

### Authentication
- `POST /api/auth/login` - Đăng nhập
- `POST /api/auth/logout` - Đăng xuất
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/change-password` - Đổi mật khẩu

### Users
- `GET /api/users` - Danh sách người dùng
- `POST /api/users` - Tạo người dùng mới
- `GET /api/users/{user_id}` - Chi tiết người dùng
- `PUT /api/users/{user_id}` - Cập nhật người dùng
- `DELETE /api/users/{user_id}` - Xóa người dùng

### Agents
- `GET /api/agents` - Danh sách đại lý
- `POST /api/agents` - Tạo đại lý mới
- `GET /api/agents/{agent_id}` - Chi tiết đại lý
- `PUT /api/agents/{agent_id}` - Cập nhật đại lý
- `DELETE /api/agents/{agent_id}` - Xóa đại lý

### Bills
- `GET /api/bills` - Danh sách hóa đơn
- `POST /api/bills/import` - Import hóa đơn từ file
- `POST /api/bills/{bill_id}/pay` - Thanh toán hóa đơn
- `GET /api/bills/overdue` - Danh sách hóa đơn quá hạn

### Transactions
- `GET /api/transactions` - Danh sách giao dịch
- `POST /api/transactions` - Tạo giao dịch mới
- `GET /api/transactions/{transaction_id}` - Chi tiết giao dịch

### Customers
- `GET /api/customers` - Danh sách khách hàng
- `POST /api/customers` - Tạo khách hàng mới
- `GET /api/customers/{customer_id}` - Chi tiết khách hàng

### Dashboard & Reports
- `GET /api/system/dashboard` - Dashboard chính
- `GET /api/reports` - Báo cáo

## ⚙️ Cấu Hình

### File `.env` (nếu có)
```env
DEBUG=True
DATABASE_URL=sqlite:///./7ty.db
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=*
CORS_ORIGINS=["*"]
```

### Cấu hình trong `config.py`
Tất cả các cài đặt có thể điều chỉnh trong file `config.py` bao gồm:
- Database connection
- JWT settings
- CORS origins
- File upload settings
- Email configuration
- Rate limiting

## 🗄️ Database

### Khởi tạo Database
Database SQLite sẽ được tạo tự động lần đầu khởi động tại `7ty_vn.db`

### Migration (Nếu cần)
Hiện tại project không dùng Alembic. Để thay đổi schema:
1. Cập nhật models.py
2. Xóa file database cũ hoặc
3. Tạo migration script thủ công

## 🧪 Testing

```bash
# Chạy tests
pytest

# Với coverage
pytest --cov
```

## 📦 Dependencies

Xem `requirements.txt` cho danh sách đầy đủ. Các package chính:
- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **sqlalchemy**: ORM
- **pydantic**: Data validation
- **python-jose**: JWT handling
- **passlib**: Password hashing
- **aiofiles**: Async file handling

## 🔧 Troubleshooting

### Server không khởi động
1. Kiểm tra port 8003 có bị chiếm dụng: `netstat -ano | findstr :8003`
2. Kiểm tra database connection
3. Xem log file `app.log`

### Database errors
1. Xóa file `7ty_vn.db` để reset
2. Kiểm tra models.py có lỗi relationship

### Import errors
1. Cài đặt lại requirements: `pip install -r requirements.txt --force-reinstall`
2. Xóa `__pycache__` folders: `find . -type d -name __pycache__ -exec rm -rf {} +`

## 📝 Logging

Tất cả logs được lưu vào file `app.log` và console. Mức độ log có thể điều chỉnh trong `main.py`

## 🔒 Security

- Passwords được hash với bcrypt
- JWT tokens được sử dụng cho authentication
- CORS được cấu hình
- Rate limiting có thể bật (trong `config.py`)

## 🚀 Deployment

Để deploy lên production:

1. Thay đổi `DEBUG=False` trong `config.py`
2. Cập nhật `SECRET_KEY` với một key mạnh
3. Dùng production ASGI server (gunicorn, etc.):
   ```bash
   gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
   ```

## 📞 Support

Để báo cáo lỗi hoặc yêu cầu features, vui lòng tạo issue trong repository.

## 📄 License

MIT License - xem file LICENSE để chi tiết

---

**Happy coding! 🎉**
