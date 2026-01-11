#!/usr/bin/env python3
import json

html = '''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>7TY.VN - Hệ Thống Quản Lý Đại Lý Điện</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --info: #06b6d4;
            --dark: #1f2937;
            --light: #f9fafb;
            --border: #e5e7eb;
            --muted: #6b7280;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }

        .app-wrapper { display: flex; height: 100vh; }
        .sidebar {
            width: 260px; background: linear-gradient(135deg, #1e293b, #0f172a); color: white;
            position: fixed; height: 100vh; left: 0; top: 0; overflow-y: auto; z-index: 1000;
            box-shadow: 2px 0 8px rgba(0,0,0,0.15);
        }
        .sidebar-header { padding: 20px 15px; border-bottom: 1px solid rgba(255,255,255,0.1); font-weight: 700; }
        .menu { padding: 10px 0; }
        .menu-item {
            padding: 12px 15px; cursor: pointer; border-left: 3px solid transparent; display: flex;
            align-items: center; gap: 12px; font-size: 13px; transition: all 0.3s; color: rgba(255,255,255,0.8);
        }
        .menu-item:hover { background: rgba(255,255,255,0.08); }
        .menu-item.active { background: var(--primary); border-left-color: white; }

        .main { margin-left: 260px; flex: 1; display: flex; flex-direction: column; }
        .header { height: 70px; background: white; border-bottom: 1px solid var(--border); padding: 0 25px;
            display: flex; justify-content: space-between; align-items: center; }
        .header-title { font-size: 18px; font-weight: 600; }
        .content { flex: 1; overflow-y: auto; padding: 25px; }
        .page { display: none; }
        .page.active { display: block; }

        .card {
            background: white; border: 1px solid var(--border); border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px;
        }
        .card-header {
            background: linear-gradient(135deg, #f9fafb, #f3f4f6); border-bottom: 1px solid var(--border);
            padding: 16px 20px; font-weight: 600;
        }
        .card-body { padding: 20px; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; margin-bottom: 25px; }
        .stat-card {
            background: white; border: 1px solid var(--border); border-radius: 10px; padding: 22px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); transition: all 0.3s;
        }
        .stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
        .stat-value { font-size: 28px; font-weight: 700; color: var(--dark); }
        .stat-label { font-size: 12px; color: var(--muted); text-transform: uppercase; }

        .table-wrapper {
            background: white; border-radius: 10px; border: 1px solid var(--border); overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .table { margin: 0; font-size: 13px; }
        .table thead { background: linear-gradient(135deg, #f9fafb, #f3f4f6); }
        .table th { border: none; padding: 14px; font-weight: 600; white-space: nowrap; }
        .table td { padding: 12px 14px; }

        .badge {
            padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600;
            display: inline-block;
        }
        .badge-success { background: rgba(16,185,129,0.12); color: var(--success); }
        .badge-danger { background: rgba(239,68,68,0.12); color: var(--danger); }
        .badge-warning { background: rgba(245,158,11,0.12); color: var(--warning); }
        .badge-info { background: rgba(6,182,212,0.12); color: var(--info); }

        .btn {
            padding: 9px 18px; border-radius: 7px; border: none; cursor: pointer; font-size: 13px;
            font-weight: 500; transition: all 0.3s; display: inline-flex; align-items: center; gap: 6px;
        }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-light { background: var(--light); color: var(--dark); border: 1px solid var(--border); }
        .btn-sm { padding: 6px 12px; font-size: 12px; }

        .form-group { margin-bottom: 16px; }
        .form-group label { font-size: 13px; font-weight: 500; margin-bottom: 6px; display: block; }
        .form-control, .form-select {
            padding: 10px 12px; border: 1px solid var(--border); border-radius: 7px; font-size: 13px;
            width: 100%;
        }
        .form-control:focus, .form-select:focus {
            border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); outline: none;
        }

        .modal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.5); z-index: 2000; align-items: center; justify-content: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white; border-radius: 10px; max-width: 600px; width: 90%;
            max-height: 85vh; overflow-y: auto; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .modal-header {
            border-bottom: 1px solid var(--border); padding: 20px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .modal-body { padding: 20px; }
        .modal-footer {
            border-top: 1px solid var(--border); padding: 16px 20px;
            display: flex; justify-content: flex-end; gap: 10px;
        }

        .alert {
            padding: 14px 16px; border-radius: 7px; margin-bottom: 16px; font-size: 13px;
            border-left: 3px solid;
        }
        .alert-success { background: rgba(16,185,129,0.1); color: var(--success); border-color: var(--success); }
        .alert-danger { background: rgba(239,68,68,0.1); color: var(--danger); border-color: var(--danger); }

        .spinner {
            border: 2px solid var(--light); border-top: 2px solid var(--primary);
            border-radius: 50%; width: 24px; height: 24px; animation: spin 0.8s linear infinite;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        @media (max-width: 768px) {
            .sidebar { width: 220px; }
            .main { margin-left: 220px; }
        }
    </style>
</head>
<body>
    <div class="app-wrapper">
        <div class="sidebar">
            <div class="sidebar-header">
                <i class="fas fa-bolt" style="color: #fbbf24;"></i> 7TY.VN
            </div>
            <div class="menu">
                <div class="menu-item active" data-page="dashboard">
                    <i class="fas fa-chart-line"></i> <span>Dashboard</span>
                </div>
                <div class="menu-item" data-page="agents">
                    <i class="fas fa-users"></i> <span>Quản lý Đại lý</span>
                </div>
                <div class="menu-item" data-page="bills">
                    <i class="fas fa-file-invoice"></i> <span>Quản lý Hóa đơn</span>
                </div>
                <div class="menu-item" data-page="customers">
                    <i class="fas fa-user-tie"></i> <span>Quản lý Khách hàng</span>
                </div>
                <div class="menu-item" data-page="transactions">
                    <i class="fas fa-exchange-alt"></i> <span>Giao dịch</span>
                </div>
                <div class="menu-item" data-page="reports">
                    <i class="fas fa-chart-bar"></i> <span>Báo cáo</span>
                </div>
                <div class="menu-item" data-page="profile">
                    <i class="fas fa-user-circle"></i> <span>Tài khoản</span>
                </div>
                <hr style="border-color: rgba(255,255,255,0.1); margin: 10px 0;">
                <div class="menu-item" onclick="logout()">
                    <i class="fas fa-sign-out-alt"></i> <span>Đăng xuất</span>
                </div>
            </div>
        </div>

        <div class="main">
            <div class="header">
                <div class="header-title">Dashboard</div>
                <div style="display: flex; align-items: center; gap: 15px;">
                    <span id="userDisplay" style="font-size: 13px; font-weight: 500;">Admin</span>
                </div>
            </div>

            <div class="content">
                <!-- Dashboard Page -->
                <div id="dashboard" class="page active">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div style="color: var(--primary); font-size: 24px; margin-bottom: 8px;"><i class="fas fa-users"></i></div>
                            <div class="stat-value" id="stat-agents">0</div>
                            <div class="stat-label">Tổng Đại lý</div>
                        </div>
                        <div class="stat-card">
                            <div style="color: var(--success); font-size: 24px; margin-bottom: 8px;"><i class="fas fa-file"></i></div>
                            <div class="stat-value" id="stat-bills">0</div>
                            <div class="stat-label">Tổng Hóa đơn</div>
                        </div>
                        <div class="stat-card">
                            <div style="color: var(--warning); font-size: 24px; margin-bottom: 8px;"><i class="fas fa-dollar-sign"></i></div>
                            <div class="stat-value" id="stat-revenue">0₫</div>
                            <div class="stat-label">Doanh thu</div>
                        </div>
                        <div class="stat-card">
                            <div style="color: var(--info); font-size: 24px; margin-bottom: 8px;"><i class="fas fa-handshake"></i></div>
                            <div class="stat-value" id="stat-customers">0</div>
                            <div class="stat-label">Khách hàng</div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header"><i class="fas fa-chart-line"></i> Doanh thu 12 tháng gần nhất</div>
                        <div class="card-body" style="height: 350px;">
                            <canvas id="chartRevenue"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Agents Page -->
                <div id="agents" class="page">
                    <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
                        <h5>Danh sách Đại lý</h5>
                        <button class="btn btn-primary" onclick="openModal('agentModal')">
                            <i class="fas fa-plus"></i> Thêm mới
                        </button>
                    </div>

                    <div class="card" style="margin-bottom: 20px;">
                        <div class="card-body">
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                                <div class="form-group">
                                    <label>Tìm kiếm</label>
                                    <input type="text" id="agentSearch" class="form-control" placeholder="Tên hoặc mã" onkeyup="loadAgents()">
                                </div>
                                <div class="form-group">
                                    <label>Trạng thái</label>
                                    <select id="agentStatus" class="form-select" onchange="loadAgents()">
                                        <option value="">Tất cả</option>
                                        <option value="active">Hoạt động</option>
                                        <option value="pending">Chờ duyệt</option>
                                        <option value="suspended">Tạm khóa</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã</th>
                                    <th>Tên</th>
                                    <th>Loại</th>
                                    <th>Trạng thái</th>
                                    <th>Số dư</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="agentsTable">
                                <tr><td colspan="6" style="text-align: center; padding: 30px;"><div class="spinner" style="margin: 0 auto;"></div></td></tr>
                            </tbody>
                        </table>
                    </div>

                    <nav style="margin-top: 20px;"><ul class="pagination" id="agentsPagination"></ul></nav>
                </div>

                <!-- Bills Page -->
                <div id="bills" class="page">
                    <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
                        <h5>Danh sách Hóa đơn</h5>
                        <button class="btn btn-primary" onclick="openModal('billModal')">
                            <i class="fas fa-plus"></i> Thêm mới
                        </button>
                    </div>

                    <div class="card" style="margin-bottom: 20px;">
                        <div class="card-body">
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                                <div class="form-group">
                                    <label>Trạng thái</label>
                                    <select id="billStatus" class="form-select" onchange="loadBills()">
                                        <option value="">Tất cả</option>
                                        <option value="in_stock">Trong kho</option>
                                        <option value="sold">Đã bán</option>
                                        <option value="paid">Đã thanh toán</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Đại lý</label>
                                    <select id="billAgent" class="form-select" onchange="loadBills()">
                                        <option value="">Tất cả</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã</th>
                                    <th>Đại lý</th>
                                    <th>Khách hàng</th>
                                    <th>Kỳ</th>
                                    <th>Số tiền</th>
                                    <th>Trạng thái</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="billsTable">
                                <tr><td colspan="7" style="text-align: center; padding: 30px;"><div class="spinner" style="margin: 0 auto;"></div></td></tr>
                            </tbody>
                        </table>
                    </div>

                    <nav style="margin-top: 20px;"><ul class="pagination" id="billsPagination"></ul></nav>
                </div>

                <!-- Customers Page -->
                <div id="customers" class="page">
                    <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
                        <h5>Danh sách Khách hàng</h5>
                        <button class="btn btn-primary" onclick="openModal('customerModal')">
                            <i class="fas fa-plus"></i> Thêm mới
                        </button>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã</th>
                                    <th>Tên</th>
                                    <th>Đại lý</th>
                                    <th>Địa chỉ</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="customersTable">
                                <tr><td colspan="5" style="text-align: center; padding: 30px; color: var(--muted);">Chưa có dữ liệu</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Transactions Page -->
                <div id="transactions" class="page">
                    <h5 style="margin-bottom: 20px;">Lịch sử Giao dịch</h5>

                    <div class="card" style="margin-bottom: 20px;">
                        <div class="card-body">
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                                <div class="form-group">
                                    <label>Loại giao dịch</label>
                                    <select id="transType" class="form-select" onchange="loadTransactions()">
                                        <option value="">Tất cả</option>
                                        <option value="deposit">Nạp tiền</option>
                                        <option value="withdraw">Rút tiền</option>
                                        <option value="bill_payment">Thanh toán HĐ</option>
                                        <option value="commission">Hoa hồng</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Trạng thái</label>
                                    <select id="transStatus" class="form-select" onchange="loadTransactions()">
                                        <option value="">Tất cả</option>
                                        <option value="pending">Chờ xử lý</option>
                                        <option value="completed">Hoàn thành</option>
                                        <option value="failed">Thất bại</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã GD</th>
                                    <th>Đại lý</th>
                                    <th>Loại</th>
                                    <th>Số tiền</th>
                                    <th>Trạng thái</th>
                                    <th>Ngày</th>
                                </tr>
                            </thead>
                            <tbody id="transTable">
                                <tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--muted);">Chưa có dữ liệu</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Reports Page -->
                <div id="reports" class="page">
                    <h5 style="margin-bottom: 20px;">Báo cáo & Thống kê</h5>
                    <div class="card">
                        <div class="card-body" style="text-align: center; padding: 60px 20px; color: var(--muted);">
                            <i class="fas fa-chart-bar" style="font-size: 48px; margin-bottom: 20px; opacity: 0.3;"></i>
                            <p>Chức năng báo cáo đang được phát triển</p>
                        </div>
                    </div>
                </div>

                <!-- Profile Page -->
                <div id="profile" class="page">
                    <h5 style="margin-bottom: 20px;">Thông tin Tài khoản</h5>
                    <div class="card" style="max-width: 600px;">
                        <div class="card-body">
                            <div class="form-group">
                                <label>Tên đăng nhập</label>
                                <input type="text" id="profileUsername" class="form-control" disabled>
                            </div>
                            <div class="form-group">
                                <label>Email</label>
                                <input type="email" id="profileEmail" class="form-control" disabled>
                            </div>
                            <div class="form-group">
                                <label>Tên đầy đủ</label>
                                <input type="text" id="profileFullName" class="form-control">
                            </div>
                            <div class="form-group">
                                <label>Số điện thoại</label>
                                <input type="tel" id="profilePhone" class="form-control">
                            </div>
                            <button class="btn btn-primary" onclick="updateProfile()">
                                <i class="fas fa-save"></i> Cập nhật
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modals -->
    <div id="agentModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div>Thêm Đại lý Mới</div>
                <button style="background: none; border: none; font-size: 20px; cursor: pointer;" onclick="closeModal('agentModal')">×</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Tên đầy đủ *</label>
                    <input type="text" id="agentName" class="form-control" placeholder="Nhập tên">
                </div>
                <div class="form-group">
                    <label>Email *</label>
                    <input type="email" id="agentEmail" class="form-control" placeholder="Nhập email">
                </div>
                <div class="form-group">
                    <label>Số điện thoại *</label>
                    <input type="tel" id="agentPhone" class="form-control" placeholder="Nhập số điện thoại">
                </div>
                <div class="form-group">
                    <label>Loại Đại lý *</label>
                    <select id="agentType" class="form-select">
                        <option value="">-- Chọn --</option>
                        <option value="individual">Cá nhân</option>
                        <option value="company">Công ty</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Mật khẩu *</label>
                    <input type="password" id="agentPassword" class="form-control" placeholder="Nhập mật khẩu">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('agentModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveAgent()"><i class="fas fa-save"></i> Lưu</button>
            </div>
        </div>
    </div>

    <div id="billModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div>Thêm Hóa đơn Mới</div>
                <button style="background: none; border: none; font-size: 20px; cursor: pointer;" onclick="closeModal('billModal')">×</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Đại lý *</label>
                    <select id="billAgentId" class="form-select"></select>
                </div>
                <div class="form-group">
                    <label>Mã Khách hàng *</label>
                    <input type="text" id="billCustomer" class="form-control">
                </div>
                <div class="form-group">
                    <label>Kỳ Tính Tiền *</label>
                    <input type="month" id="billPeriod" class="form-control">
                </div>
                <div class="form-group">
                    <label>Số Tiền *</label>
                    <input type="number" id="billAmount" class="form-control" placeholder="0">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('billModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveBill()"><i class="fas fa-save"></i> Lưu</button>
            </div>
        </div>
    </div>

    <div id="customerModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div>Thêm Khách hàng Mới</div>
                <button style="background: none; border: none; font-size: 20px; cursor: pointer;" onclick="closeModal('customerModal')">×</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Mã Khách hàng *</label>
                    <input type="text" id="customerCode" class="form-control">
                </div>
                <div class="form-group">
                    <label>Tên Khách hàng *</label>
                    <input type="text" id="customerName" class="form-control">
                </div>
                <div class="form-group">
                    <label>Địa chỉ *</label>
                    <input type="text" id="customerAddress" class="form-control">
                </div>
                <div class="form-group">
                    <label>Số điện thoại</label>
                    <input type="tel" id="customerPhone" class="form-control">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('customerModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveCustomer()"><i class="fas fa-save"></i> Lưu</button>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <script>
        const API = 'http://localhost:8000/api';
        let token = localStorage.getItem('access_token');
        let user = null;

        document.addEventListener('DOMContentLoaded', init);

        async function init() {
            if (!token) { window.location.href = '/login.html'; return; }

            try {
                const res = await fetch(API + '/users/me', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('Auth failed');
                user = await res.json();
                document.getElementById('userDisplay').textContent = user.full_name || user.username;

                setupMenuListeners();
                loadPage('dashboard');
                loadAgentsList(); // Load for modals
            } catch (e) {
                console.error(e);
                localStorage.removeItem('access_token');
                window.location.href = '/login.html';
            }
        }

        function setupMenuListeners() {
            document.querySelectorAll('.menu-item').forEach(item => {
                item.addEventListener('click', () => {
                    const page = item.dataset.page;
                    if (page) {
                        document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
                        item.classList.add('active');

                        const titles = {
                            dashboard: 'Dashboard',
                            agents: 'Quản lý Đại lý',
                            bills: 'Quản lý Hóa đơn',
                            customers: 'Quản lý Khách hàng',
                            transactions: 'Giao dịch',
                            reports: 'Báo cáo & Thống kê',
                            profile: 'Tài khoản'
                        };
                        document.querySelector('.header-title').textContent = titles[page] || page;
                        loadPage(page);
                    }
                });
            });
        }

        function loadPage(page) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(page).classList.add('active');

            if (page === 'dashboard') loadDashboard();
            else if (page === 'agents') loadAgents();
            else if (page === 'bills') loadBills();
            else if (page === 'transactions') loadTransactions();
            else if (page === 'profile') loadProfile();
        }

        async function loadDashboard() {
            try {
                const res = await fetch(API + '/system/dashboard', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                document.getElementById('stat-agents').textContent = data.total_agents || 0;
                document.getElementById('stat-bills').textContent = data.total_bills || 0;
                document.getElementById('stat-customers').textContent = data.total_customers || 0;

                const revenue = new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(data.total_revenue || 0);
                document.getElementById('stat-revenue').textContent = revenue;

                if (data.monthly_revenue) {
                    const ctx = document.getElementById('chartRevenue');
                    new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: Object.keys(data.monthly_revenue),
                            datasets: [{
                                label: 'Doanh thu',
                                data: Object.values(data.monthly_revenue),
                                borderColor: '#2563eb',
                                backgroundColor: 'rgba(37,99,235,0.1)',
                                tension: 0.4,
                                fill: true,
                                pointRadius: 5,
                                pointBackgroundColor: '#2563eb'
                            }]
                        },
                        options: { responsive: true, maintainAspectRatio: true }
                    });
                }
            } catch (e) {
                console.error('Dashboard error:', e);
            }
        }

        async function loadAgents(page = 1) {
            try {
                let url = API + '/agents?page=' + page + '&limit=10';
                const search = document.getElementById('agentSearch')?.value;
                const status = document.getElementById('agentStatus')?.value;

                if (search) url += '&search=' + search;
                if (status) url += '&status=' + status;

                const res = await fetch(url, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                let html = '';
                if (data.data && data.data.length) {
                    data.data.forEach(agent => {
                        html += '<tr>';
                        html += '<td>' + (agent.agent_code || '-') + '</td>';
                        html += '<td>' + (agent.user?.full_name || '-') + '</td>';
                        html += '<td>' + (agent.agent_type === 'individual' ? 'Cá nhân' : 'Công ty') + '</td>';
                        html += '<td>' + getStatusBadge(agent.status) + '</td>';
                        html += '<td>' + formatMoney(agent.balance || 0) + '</td>';
                        html += '<td><button class="btn btn-sm btn-light"><i class="fas fa-eye"></i></button></td>';
                        html += '</tr>';
                    });
                } else {
                    html = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--muted);">Chưa có dữ liệu</td></tr>';
                }
                document.getElementById('agentsTable').innerHTML = html;
            } catch (e) {
                console.error(e);
            }
        }

        async function loadAgentsList() {
            try {
                const res = await fetch(API + '/agents?limit=100', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                const data = await res.json();

                let html = '<option value="">-- Chọn --</option>';
                if (data.data) {
                    data.data.forEach(agent => {
                        html += '<option value="' + agent.id + '">' + (agent.user?.full_name || agent.agent_code) + '</option>';
                    });
                }

                document.getElementById('billAgentId').innerHTML = html;
                document.getElementById('billAgent').innerHTML = html;
                document.getElementById('customerAgent').innerHTML = html;
            } catch (e) {
                console.error(e);
            }
        }

        async function loadBills(page = 1) {
            try {
                let url = API + '/bills?page=' + page + '&limit=10';
                const status = document.getElementById('billStatus')?.value;
                if (status) url += '&status=' + status;

                const res = await fetch(url, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                let html = '';
                if (data.data && data.data.length) {
                    data.data.forEach(bill => {
                        html += '<tr>';
                        html += '<td>' + (bill.bill_code || '-') + '</td>';
                        html += '<td>' + (bill.agent?.agent_code || '-') + '</td>';
                        html += '<td>' + (bill.customer_code || '-') + '</td>';
                        html += '<td>' + (bill.period || '-') + '</td>';
                        html += '<td>' + formatMoney(bill.total_amount || 0) + '</td>';
                        html += '<td>' + getStatusBadge(bill.status) + '</td>';
                        html += '<td><button class="btn btn-sm btn-light"><i class="fas fa-edit"></i></button></td>';
                        html += '</tr>';
                    });
                } else {
                    html = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--muted);">Chưa có dữ liệu</td></tr>';
                }
                document.getElementById('billsTable').innerHTML = html;
            } catch (e) {
                console.error(e);
            }
        }

        async function loadTransactions(page = 1) {
            try {
                let url = API + '/transactions?page=' + page + '&limit=10';
                const type = document.getElementById('transType')?.value;
                const status = document.getElementById('transStatus')?.value;

                if (type) url += '&transaction_type=' + type;
                if (status) url += '&status=' + status;

                const res = await fetch(url, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                let html = '';
                if (data.data && data.data.length) {
                    data.data.forEach(trans => {
                        html += '<tr>';
                        html += '<td>' + (trans.transaction_code || '-') + '</td>';
                        html += '<td>' + (trans.agent?.agent_code || '-') + '</td>';
                        html += '<td>' + (trans.transaction_type || '-') + '</td>';
                        html += '<td>' + formatMoney(trans.amount || 0) + '</td>';
                        html += '<td>' + getStatusBadge(trans.status) + '</td>';
                        html += '<td>' + new Date(trans.created_at).toLocaleDateString('vi-VN') + '</td>';
                        html += '</tr>';
                    });
                } else {
                    html = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--muted);">Chưa có dữ liệu</td></tr>';
                }
                document.getElementById('transTable').innerHTML = html;
            } catch (e) {
                console.error(e);
            }
        }

        async function loadProfile() {
            if (!user) return;
            document.getElementById('profileUsername').value = user.username || '';
            document.getElementById('profileEmail').value = user.email || '';
            document.getElementById('profileFullName').value = user.full_name || '';
            document.getElementById('profilePhone').value = user.phone || '';
        }

        async function updateProfile() {
            try {
                const res = await fetch(API + '/users/me', {
                    method: 'PUT',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        full_name: document.getElementById('profileFullName').value,
                        phone: document.getElementById('profilePhone').value
                    })
                });

                if (!res.ok) throw new Error('Update failed');
                alert('✓ Cập nhật thành công');
            } catch (e) {
                alert('✗ Lỗi: ' + e.message);
            }
        }

        async function saveAgent() {
            try {
                const res = await fetch(API + '/agents/with-user', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        user: {
                            full_name: document.getElementById('agentName').value,
                            email: document.getElementById('agentEmail').value,
                            phone: document.getElementById('agentPhone').value,
                            password: document.getElementById('agentPassword').value
                        },
                        agent_type: document.getElementById('agentType').value
                    })
                });

                if (!res.ok) throw new Error('Save failed');
                alert('✓ Thêm đại lý thành công');
                closeModal('agentModal');
                loadAgents();
            } catch (e) {
                alert('✗ Lỗi: ' + e.message);
            }
        }

        async function saveBill() {
            try {
                const res = await fetch(API + '/bills', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        agent_id: parseInt(document.getElementById('billAgentId').value),
                        customer_code: document.getElementById('billCustomer').value,
                        period: document.getElementById('billPeriod').value,
                        total_amount: parseFloat(document.getElementById('billAmount').value)
                    })
                });

                if (!res.ok) throw new Error('Save failed');
                alert('✓ Thêm hóa đơn thành công');
                closeModal('billModal');
                loadBills();
            } catch (e) {
                alert('✗ Lỗi: ' + e.message);
            }
        }

        function saveCustomer() {
            alert('Chức năng đang phát triển');
        }

        function getStatusBadge(status) {
            const badges = {
                'active': '<span class="badge badge-success">Hoạt động</span>',
                'pending': '<span class="badge badge-warning">Chờ duyệt</span>',
                'suspended': '<span class="badge badge-danger">Tạm khóa</span>',
                'sold': '<span class="badge badge-success">Đã bán</span>',
                'paid': '<span class="badge badge-success">Đã thanh toán</span>',
                'completed': '<span class="badge badge-success">Hoàn thành</span>',
                'failed': '<span class="badge badge-danger">Thất bại</span>',
                'in_stock': '<span class="badge badge-info">Trong kho</span>'
            };
            return badges[status] || '<span class="badge badge-info">' + (status || 'N/A') + '</span>';
        }

        function formatMoney(value) {
            return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value);
        }

        function openModal(id) {
            document.getElementById(id).classList.add('active');
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
        }

        function logout() {
            localStorage.removeItem('access_token');
            window.location.href = '/login.html';
        }
    </script>
</body>
</html>
'''

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("✅ Generated comprehensive app.html")
print(f"Size: {len(html) / 1024:.1f} KB")
print(f"Lines: {len(html.splitlines())}")
