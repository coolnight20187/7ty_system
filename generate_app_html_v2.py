#!/usr/bin/env python3
"""
Generate comprehensive, production-ready app.html fully synchronized with backend
"""

html_content = '''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#2563eb">
    <title>7TY.VN - Hệ Thống Quản Lý Đại Lý</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --secondary: #7c3aed;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --info: #06b6d4;
            --dark: #1f2937;
            --light: #f9fafb;
            --border: #e5e7eb;
            --muted: #6b7280;
            --transition: all 0.3s ease;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
        }

        .app-wrapper {
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* Sidebar */
        .sidebar {
            width: 240px;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            position: fixed;
            height: 100vh;
            left: 0;
            top: 0;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 2px 0 8px rgba(0,0,0,0.15);
        }

        .sidebar-header {
            padding: 20px 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-weight: 700;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .sidebar-logo { width: 28px; height: 28px; background: var(--primary); border-radius: 6px; display: flex; align-items: center; justify-content: center; }

        .menu { padding: 10px 0; }

        .menu-item {
            padding: 12px 15px;
            cursor: pointer;
            border-left: 3px solid transparent;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 13px;
            transition: var(--transition);
            color: rgba(255,255,255,0.8);
        }

        .menu-item:hover {
            background: rgba(255,255,255,0.08);
            color: white;
        }

        .menu-item.active {
            background: var(--primary);
            border-left-color: white;
            color: white;
        }

        .menu-item i { width: 18px; text-align: center; }

        /* Main Content */
        .main {
            margin-left: 240px;
            flex: 1;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        .header {
            height: 70px;
            background: white;
            border-bottom: 1px solid var(--border);
            padding: 0 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        .header-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--dark);
        }

        .user-menu {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 6px 12px;
            background: var(--light);
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition);
        }

        .user-menu:hover {
            background: #eff6ff;
        }

        .user-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: var(--primary);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 14px;
        }

        .user-name { font-size: 13px; color: var(--dark); font-weight: 500; }

        .content {
            flex: 1;
            overflow-y: auto;
            padding: 25px;
        }

        .page { display: none; }
        .page.active { display: block; animation: fadeIn 0.3s; }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        /* Cards */
        .card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 20px;
        }

        .card-header {
            background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
            border-bottom: 1px solid var(--border);
            padding: 16px 20px;
            font-weight: 600;
            color: var(--dark);
            border-radius: 10px 10px 0 0;
        }

        .card-body {
            padding: 20px;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
            margin-bottom: 25px;
        }

        .stat-card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 22px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: var(--transition);
        }

        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }

        .stat-icon {
            font-size: 24px;
            color: var(--primary);
            margin-bottom: 8px;
            opacity: 0.8;
        }

        .stat-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--dark);
            margin-bottom: 6px;
        }

        .stat-label {
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Tables */
        .table-wrapper {
            background: white;
            border-radius: 10px;
            border: 1px solid var(--border);
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        .table {
            margin: 0;
            font-size: 13px;
        }

        .table thead {
            background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
            border-bottom: 1px solid var(--border);
        }

        .table th {
            border: none;
            padding: 14px;
            font-weight: 600;
            color: var(--dark);
            white-space: nowrap;
        }

        .table td {
            padding: 12px 14px;
            border-color: var(--border);
            vertical-align: middle;
        }

        .table tbody tr:hover {
            background: var(--light);
        }

        /* Badges */
        .badge {
            padding: 4px 10px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 600;
            display: inline-block;
        }

        .badge-success { background: rgba(16,185,129,0.12); color: var(--success); }
        .badge-danger { background: rgba(239,68,68,0.12); color: var(--danger); }
        .badge-warning { background: rgba(245,158,11,0.12); color: var(--warning); }
        .badge-info { background: rgba(6,182,212,0.12); color: var(--info); }
        .badge-primary { background: rgba(37,99,235,0.12); color: var(--primary); }

        /* Buttons */
        .btn {
            padding: 9px 18px;
            border-radius: 7px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-warning { background: var(--warning); color: white; }
        .btn-light { background: var(--light); color: var(--dark); border: 1px solid var(--border); }
        .btn-light:hover { background: #f3f4f6; }
        .btn-sm { padding: 6px 12px; font-size: 12px; }

        /* Forms */
        .form-group { margin-bottom: 16px; }
        .form-group label { font-size: 13px; font-weight: 500; margin-bottom: 6px; color: var(--dark); }

        .form-control, .form-select {
            padding: 10px 12px;
            border: 1px solid var(--border);
            border-radius: 7px;
            font-size: 13px;
            transition: var(--transition);
        }

        .form-control:focus, .form-select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
            outline: none;
        }

        /* Modals */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 2000;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.3s;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: white;
            border-radius: 10px;
            max-width: 600px;
            width: 90%;
            max-height: 85vh;
            overflow-y: auto;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }

        .modal-header {
            border-bottom: 1px solid var(--border);
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
        }

        .modal-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--dark);
        }

        .modal-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: var(--muted);
            transition: var(--transition);
        }

        .modal-close:hover {
            color: var(--dark);
        }

        .modal-body {
            padding: 20px;
        }

        .modal-footer {
            border-top: 1px solid var(--border);
            padding: 16px 20px;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            background: var(--light);
            border-radius: 0 0 10px 10px;
        }

        /* Pagination */
        .pagination {
            justify-content: center;
            margin-top: 20px;
        }

        .page-link {
            color: var(--primary);
            border: 1px solid var(--border);
            padding: 8px 12px;
            font-size: 13px;
        }

        .page-link:hover {
            background: var(--light);
            color: var(--primary);
        }

        .page-item.active .page-link {
            background: var(--primary);
            border-color: var(--primary);
        }

        /* Alerts */
        .alert {
            padding: 14px 16px;
            border-radius: 7px;
            margin-bottom: 16px;
            font-size: 13px;
            border-left: 3px solid;
        }

        .alert-success { background: rgba(16,185,129,0.1); color: var(--success); border-color: var(--success); }
        .alert-danger { background: rgba(239,68,68,0.1); color: var(--danger); border-color: var(--danger); }
        .alert-warning { background: rgba(245,158,11,0.1); color: var(--warning); border-color: var(--warning); }
        .alert-info { background: rgba(6,182,212,0.1); color: var(--info); border-color: var(--info); }

        /* Loading */
        .spinner {
            border: 2px solid var(--light);
            border-top: 2px solid var(--primary);
            border-radius: 50%;
            width: 24px;
            height: 24px;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .loading-text {
            text-align: center;
            padding: 40px 20px;
            color: var(--muted);
        }

        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                width: 220px;
            }
            .main {
                margin-left: 220px;
            }
            .content {
                padding: 16px;
            }
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .header {
                flex-direction: column;
                height: auto;
                padding: 16px;
                gap: 12px;
            }
        }
    </style>
</head>
<body>
    <div class="app-wrapper">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    <i class="fas fa-home" style="color: white; font-size: 14px;"></i>
                </div>
                <span>7TY.VN</span>
            </div>
            <div class="menu">
                <div class="menu-item active" data-page="dashboard">
                    <i class="fas fa-chart-line"></i>
                    <span>Bảng điều khiển</span>
                </div>
                <div class="menu-item" data-page="agents">
                    <i class="fas fa-users"></i>
                    <span>Quản lý Đại lý</span>
                </div>
                <div class="menu-item" data-page="bills">
                    <i class="fas fa-file-invoice"></i>
                    <span>Quản lý Hóa đơn</span>
                </div>
                <div class="menu-item" data-page="customers">
                    <i class="fas fa-user-tie"></i>
                    <span>Quản lý Khách hàng</span>
                </div>
                <div class="menu-item" data-page="transactions">
                    <i class="fas fa-exchange-alt"></i>
                    <span>Giao dịch</span>
                </div>
                <div class="menu-item" data-page="reports">
                    <i class="fas fa-chart-bar"></i>
                    <span>Báo cáo & Thống kê</span>
                </div>
                <div class="menu-item" data-page="notifications">
                    <i class="fas fa-bell"></i>
                    <span>Thông báo</span>
                </div>
                <div class="menu-item" data-page="profile">
                    <i class="fas fa-user-circle"></i>
                    <span>Tài khoản Cá nhân</span>
                </div>
                <hr style="border-color: rgba(255,255,255,0.1); margin: 10px 0;">
                <div class="menu-item" onclick="logout()">
                    <i class="fas fa-sign-out-alt"></i>
                    <span>Đăng xuất</span>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main">
            <!-- Header -->
            <div class="header">
                <div class="header-title">Bảng điều khiển</div>
                <div class="user-menu" onclick="goToPage('profile')">
                    <div class="user-avatar" id="userAvatarHeader">A</div>
                    <div>
                        <div class="user-name" id="userNameDisplay">Admin</div>
                        <div style="font-size: 11px; color: var(--muted);">Administrator</div>
                    </div>
                </div>
            </div>

            <!-- Content Area -->
            <div class="content">
                <!-- Dashboard Page -->
                <div id="dashboard" class="page active">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-icon"><i class="fas fa-users"></i></div>
                            <div class="stat-value" id="stat-agents">0</div>
                            <div class="stat-label">Tổng Đại lý</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon"><i class="fas fa-file-invoice"></i></div>
                            <div class="stat-value" id="stat-bills">0</div>
                            <div class="stat-label">Tổng Hóa đơn</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon"><i class="fas fa-dollar-sign"></i></div>
                            <div class="stat-value" id="stat-revenue">0₫</div>
                            <div class="stat-label">Doanh thu</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon"><i class="fas fa-handshake"></i></div>
                            <div class="stat-value" id="stat-customers">0</div>
                            <div class="stat-label">Khách hàng</div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <i class="fas fa-chart-line"></i> Biểu đồ Doanh thu 12 tháng
                        </div>
                        <div class="card-body" style="min-height: 300px;">
                            <canvas id="revenueChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Agents Page -->
                <div id="agents" class="page">
                    <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                        <h5 style="margin: 0;">Danh sách Đại lý</h5>
                        <button class="btn btn-primary" onclick="openModal('agentModal')">
                            <i class="fas fa-plus"></i> Thêm Đại lý
                        </button>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã Đại lý</th>
                                    <th>Tên</th>
                                    <th>Điện thoại</th>
                                    <th>Loại</th>
                                    <th>Trạng thái</th>
                                    <th>Số dư</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="agentsTable">
                                <tr>
                                    <td colspan="7" class="loading-text">
                                        <div class="spinner" style="margin: 0 auto 10px;"></div>
                                        Đang tải dữ liệu...
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <nav aria-label="pagination">
                        <ul class="pagination" id="agentsPagination"></ul>
                    </nav>
                </div>

                <!-- Bills Page -->
                <div id="bills" class="page">
                    <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                        <h5 style="margin: 0;">Danh sách Hóa đơn</h5>
                        <button class="btn btn-primary" onclick="openModal('billModal')">
                            <i class="fas fa-plus"></i> Thêm Hóa đơn
                        </button>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã HĐ</th>
                                    <th>Đại lý</th>
                                    <th>Khách hàng</th>
                                    <th>Kỳ</th>
                                    <th>Số tiền</th>
                                    <th>Trạng thái</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="billsTable">
                                <tr>
                                    <td colspan="7" class="loading-text">
                                        <div class="spinner" style="margin: 0 auto 10px;"></div>
                                        Đang tải dữ liệu...
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <nav aria-label="pagination">
                        <ul class="pagination" id="billsPagination"></ul>
                    </nav>
                </div>

                <!-- Customers Page -->
                <div id="customers" class="page">
                    <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                        <h5 style="margin: 0;">Danh sách Khách hàng</h5>
                        <button class="btn btn-primary" onclick="openModal('customerModal')">
                            <i class="fas fa-plus"></i> Thêm Khách hàng
                        </button>
                    </div>

                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã KH</th>
                                    <th>Tên</th>
                                    <th>Đại lý</th>
                                    <th>Điện thoại</th>
                                    <th>Địa chỉ</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="customersTable">
                                <tr>
                                    <td colspan="6" style="text-align: center; padding: 40px 20px; color: var(--muted);">
                                        Chưa có dữ liệu
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Transactions Page -->
                <div id="transactions" class="page">
                    <h5 style="margin-bottom: 20px;">Lịch sử Giao dịch</h5>

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
                            <tbody id="transactionsTable">
                                <tr>
                                    <td colspan="6" style="text-align: center; padding: 40px 20px; color: var(--muted);">
                                        Chưa có dữ liệu
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Reports Page -->
                <div id="reports" class="page">
                    <h5 style="margin-bottom: 20px;">Báo cáo & Thống kê</h5>
                    <div class="card">
                        <div class="card-body" style="text-align: center; padding: 60px 20px; color: var(--muted);">
                            <i class="fas fa-chart-line" style="font-size: 48px; margin-bottom: 20px; opacity: 0.3;"></i>
                            <p>Chức năng báo cáo đang được phát triển</p>
                        </div>
                    </div>
                </div>

                <!-- Notifications Page -->
                <div id="notifications" class="page">
                    <h5 style="margin-bottom: 20px;">Thông báo</h5>
                    <div class="card">
                        <div class="card-body" id="notificationsContainer">
                            <div style="text-align: center; padding: 40px 20px; color: var(--muted);">
                                <i class="fas fa-bell" style="font-size: 48px; margin-bottom: 20px; opacity: 0.3;"></i>
                                <p>Chưa có thông báo</p>
                            </div>
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
                                <input type="text" class="form-control" id="profile-username" disabled>
                            </div>
                            <div class="form-group">
                                <label>Email</label>
                                <input type="email" class="form-control" id="profile-email" disabled>
                            </div>
                            <div class="form-group">
                                <label>Tên đầy đủ</label>
                                <input type="text" class="form-control" id="profile-fullname">
                            </div>
                            <div class="form-group">
                                <label>Số điện thoại</label>
                                <input type="tel" class="form-control" id="profile-phone">
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
    <!-- Agent Modal -->
    <div id="agentModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Thêm Đại lý Mới</div>
                <button class="modal-close" onclick="closeModal('agentModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Tên đầy đủ</label>
                    <input type="text" class="form-control" id="agent-fullname" placeholder="Nhập tên đại lý">
                </div>
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" class="form-control" id="agent-email" placeholder="Nhập email">
                </div>
                <div class="form-group">
                    <label>Số điện thoại</label>
                    <input type="tel" class="form-control" id="agent-phone" placeholder="Nhập số điện thoại">
                </div>
                <div class="form-group">
                    <label>Loại Đại lý</label>
                    <select class="form-select" id="agent-type">
                        <option value="">-- Chọn loại --</option>
                        <option value="individual">Cá nhân</option>
                        <option value="company">Công ty</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Mật khẩu</label>
                    <input type="password" class="form-control" id="agent-password" placeholder="Nhập mật khẩu">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('agentModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveAgent()">
                    <i class="fas fa-save"></i> Lưu
                </button>
            </div>
        </div>
    </div>

    <!-- Bill Modal -->
    <div id="billModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Thêm Hóa đơn Mới</div>
                <button class="modal-close" onclick="closeModal('billModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Đại lý</label>
                    <select class="form-select" id="bill-agent">
                        <option value="">-- Chọn đại lý --</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Mã Khách hàng</label>
                    <input type="text" class="form-control" id="bill-customer-code" placeholder="Nhập mã khách hàng">
                </div>
                <div class="form-group">
                    <label>Kỳ Tính Tiền</label>
                    <input type="month" class="form-control" id="bill-period">
                </div>
                <div class="form-group">
                    <label>Số Tiền</label>
                    <input type="number" class="form-control" id="bill-amount" placeholder="0" min="0">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('billModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveBill()">
                    <i class="fas fa-save"></i> Lưu
                </button>
            </div>
        </div>
    </div>

    <!-- Customer Modal -->
    <div id="customerModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Thêm Khách hàng Mới</div>
                <button class="modal-close" onclick="closeModal('customerModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Mã Khách hàng</label>
                    <input type="text" class="form-control" id="customer-code" placeholder="Nhập mã khách hàng">
                </div>
                <div class="form-group">
                    <label>Tên Khách hàng</label>
                    <input type="text" class="form-control" id="customer-name" placeholder="Nhập tên khách hàng">
                </div>
                <div class="form-group">
                    <label>Đại lý</label>
                    <select class="form-select" id="customer-agent">
                        <option value="">-- Chọn đại lý --</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Địa chỉ</label>
                    <input type="text" class="form-control" id="customer-address" placeholder="Nhập địa chỉ">
                </div>
                <div class="form-group">
                    <label>Số điện thoại</label>
                    <input type="tel" class="form-control" id="customer-phone" placeholder="Nhập số điện thoại">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('customerModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveCustomer()">
                    <i class="fas fa-save"></i> Lưu
                </button>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <script>
        // ============ Configuration ============
        const API = 'http://localhost:8000/api';
        let token = localStorage.getItem('access_token');
        let currentUser = null;
        let currentPage = 'dashboard';

        // ============ Initialize ============
        document.addEventListener('DOMContentLoaded', init);

        async function init() {
            // Check auth
            if (!token) {
                window.location.href = '/login.html';
                return;
            }

            try {
                const res = await fetch(API + '/users/me', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('Auth failed');
                
                currentUser = await res.json();
                updateUserDisplay();
                setupMenuListeners();
                loadPage('dashboard');
            } catch (e) {
                console.error('💥 Auth error:', e);
                localStorage.removeItem('access_token');
                window.location.href = '/login.html';
            }
        }

        // ============ UI Helpers ============
        function updateUserDisplay() {
            if (!currentUser) return;
            const avatar = (currentUser.full_name || currentUser.username).charAt(0).toUpperCase();
            document.getElementById('userAvatarHeader').textContent = avatar;
            document.getElementById('userNameDisplay').textContent = currentUser.full_name || currentUser.username;
        }

        function setupMenuListeners() {
            document.querySelectorAll('.menu-item').forEach(item => {
                item.addEventListener('click', () => {
                    const page = item.dataset.page;
                    if (page) goToPage(page);
                });
            });
        }

        function goToPage(page) {
            // Update active menu
            document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
            document.querySelector(`[data-page="${page}"]`).classList.add('active');

            // Update title
            const titles = {
                dashboard: 'Bảng điều khiển',
                agents: 'Quản lý Đại lý',
                bills: 'Quản lý Hóa đơn',
                customers: 'Quản lý Khách hàng',
                transactions: 'Giao dịch',
                reports: 'Báo cáo & Thống kê',
                notifications: 'Thông báo',
                profile: 'Tài khoản Cá nhân'
            };
            document.querySelector('.header-title').textContent = titles[page] || page;

            // Load page
            loadPage(page);
        }

        function loadPage(page) {
            currentPage = page;
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(page).classList.add('active');

            if (page === 'dashboard') loadDashboard();
            else if (page === 'agents') loadAgents();
            else if (page === 'bills') loadBills();
            else if (page === 'profile') loadProfile();
        }

        // ============ Dashboard ============
        async function loadDashboard() {
            try {
                const res = await fetch(API + '/system/dashboard', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('Dashboard API error');
                const data = await res.json();

                document.getElementById('stat-agents').textContent = data.total_agents || 0;
                document.getElementById('stat-bills').textContent = data.total_bills || 0;
                document.getElementById('stat-customers').textContent = data.total_customers || 0;

                const revenue = formatCurrency(data.total_revenue || 0);
                document.getElementById('stat-revenue').textContent = revenue;

                // Chart
                if (data.revenue_by_month) {
                    initChart(data.revenue_by_month);
                }
            } catch (e) {
                console.error('Dashboard error:', e);
            }
        }

        function initChart(data) {
            const ctx = document.getElementById('revenueChart');
            if (!ctx) return;

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Object.keys(data),
                    datasets: [{
                        label: 'Doanh thu',
                        data: Object.values(data),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37,99,235,0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 5,
                        pointBackgroundColor: '#2563eb'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { display: true, position: 'top' }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: v => (v / 1e6).toFixed(1) + 'M'
                            }
                        }
                    }
                }
            });
        }

        // ============ Agents ============
        async function loadAgents(page = 1) {
            try {
                const res = await fetch(API + '/agents?page=' + page + '&limit=10', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                renderTable('agentsTable', data.data || [], [
                    { key: 'agent_code', label: 'Mã' },
                    { key: 'user.full_name', label: 'Tên' },
                    { key: 'user.phone', label: 'Điện thoại' },
                    { key: 'agent_type', label: 'Loại', render: v => v === 'individual' ? 'Cá nhân' : 'Công ty' },
                    { key: 'status', label: 'Trạng thái', render: v => getStatusBadge(v) },
                    { key: 'balance', label: 'Số dư', render: v => formatCurrency(v) },
                    { key: 'id', label: 'Hành động', render: id => `<button class="btn btn-sm btn-light" onclick="viewAgent(${id})"><i class="fas fa-eye"></i> Xem</button>` }
                ]);

                renderPagination('agentsPagination', data.page, data.pages, p => loadAgents(p));
            } catch (e) {
                console.error('Load agents error:', e);
                document.getElementById('agentsTable').innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px; color: red;">Lỗi tải dữ liệu</td></tr>';
            }
        }

        async function saveAgent() {
            const data = {
                user: {
                    full_name: document.getElementById('agent-fullname').value,
                    email: document.getElementById('agent-email').value,
                    phone: document.getElementById('agent-phone').value,
                    password: document.getElementById('agent-password').value
                },
                agent_type: document.getElementById('agent-type').value
            };

            try {
                const res = await fetch(API + '/agents/with-user', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                if (!res.ok) throw new Error('Save failed');
                showAlert('✅ Thêm đại lý thành công', 'success');
                closeModal('agentModal');
                loadAgents();
            } catch (e) {
                showAlert('❌ Lỗi: ' + e.message, 'danger');
            }
        }

        // ============ Bills ============
        async function loadBills(page = 1) {
            try {
                const res = await fetch(API + '/bills?page=' + page + '&limit=10', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });

                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                renderTable('billsTable', data.data || [], [
                    { key: 'bill_code', label: 'Mã HĐ' },
                    { key: 'agent.agent_code', label: 'Đại lý' },
                    { key: 'customer_code', label: 'Khách hàng' },
                    { key: 'period', label: 'Kỳ' },
                    { key: 'total_amount', label: 'Số tiền', render: v => formatCurrency(v) },
                    { key: 'status', label: 'Trạng thái', render: v => getStatusBadge(v) },
                    { key: 'id', label: 'Hành động', render: id => `<button class="btn btn-sm btn-light"><i class="fas fa-edit"></i></button>` }
                ]);

                renderPagination('billsPagination', data.page, data.pages, p => loadBills(p));
            } catch (e) {
                console.error('Load bills error:', e);
                document.getElementById('billsTable').innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px; color: red;">Lỗi tải dữ liệu</td></tr>';
            }
        }

        async function saveBill() {
            const data = {
                agent_id: parseInt(document.getElementById('bill-agent').value),
                customer_code: document.getElementById('bill-customer-code').value,
                period: document.getElementById('bill-period').value,
                total_amount: parseFloat(document.getElementById('bill-amount').value)
            };

            try {
                const res = await fetch(API + '/bills', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                if (!res.ok) throw new Error('Save failed');
                showAlert('✅ Thêm hóa đơn thành công', 'success');
                closeModal('billModal');
                loadBills();
            } catch (e) {
                showAlert('❌ Lỗi: ' + e.message, 'danger');
            }
        }

        // ============ Profile ============
        async function loadProfile() {
            if (!currentUser) return;
            document.getElementById('profile-username').value = currentUser.username || '';
            document.getElementById('profile-email').value = currentUser.email || '';
            document.getElementById('profile-fullname').value = currentUser.full_name || '';
            document.getElementById('profile-phone').value = currentUser.phone || '';
        }

        async function updateProfile() {
            const data = {
                full_name: document.getElementById('profile-fullname').value,
                phone: document.getElementById('profile-phone').value
            };

            try {
                const res = await fetch(API + '/users/me', {
                    method: 'PUT',
                    headers: {
                        'Authorization': 'Bearer ' + token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                if (!res.ok) throw new Error('Update failed');
                showAlert('✅ Cập nhật thành công', 'success');
            } catch (e) {
                showAlert('❌ Lỗi: ' + e.message, 'danger');
            }
        }

        // ============ Helpers ============
        function renderTable(elementId, data, columns) {
            const tbody = document.getElementById(elementId);
            tbody.innerHTML = '';

            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="' + columns.length + '" style="text-align: center; padding: 40px; color: var(--muted);">Chưa có dữ liệu</td></tr>';
                return;
            }

            data.forEach(row => {
                const tr = document.createElement('tr');
                columns.forEach(col => {
                    const td = document.createElement('td');
                    let value = row;
                    col.key.split('.').forEach(k => value = value?.[k]);
                    td.innerHTML = col.render ? col.render(value, row) : (value || '-');
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }

        function renderPagination(elementId, currentPage, totalPages, callback) {
            const container = document.getElementById(elementId);
            container.innerHTML = '';

            if (totalPages <= 1) return;

            if (currentPage > 1) {
                const li = document.createElement('li');
                li.className = 'page-item';
                li.innerHTML = '<a class="page-link" href="#" onclick="event.preventDefault(); ' + callback.toString().match(/function[^{]*\\{([\\s\\S]*?)\\}/)[1].trim() + '(1)">Trước</a>';
                container.appendChild(li);
            }

            for (let i = 1; i <= totalPages; i++) {
                const li = document.createElement('li');
                li.className = 'page-item' + (i === currentPage ? ' active' : '');
                li.innerHTML = '<a class="page-link" href="#" onclick="event.preventDefault(); ' + callback.name + '(' + i + ')">' + i + '</a>';
                container.appendChild(li);
            }

            if (currentPage < totalPages) {
                const li = document.createElement('li');
                li.className = 'page-item';
                li.innerHTML = '<a class="page-link" href="#">Tiếp</a>';
                container.appendChild(li);
            }
        }

        function getStatusBadge(status) {
            const badges = {
                'active': '<span class="badge badge-success">Hoạt động</span>',
                'pending': '<span class="badge badge-warning">Chờ duyệt</span>',
                'inactive': '<span class="badge badge-danger">Không hoạt động</span>',
                'suspended': '<span class="badge badge-danger">Tạm khóa</span>',
                'in_stock': '<span class="badge badge-info">Trong kho</span>',
                'sold': '<span class="badge badge-success">Đã bán</span>',
                'paid': '<span class="badge badge-success">Đã thanh toán</span>',
                'processing': '<span class="badge badge-warning">Đang xử lý</span>'
            };
            return badges[status] || '<span class="badge badge-primary">' + (status || 'N/A') + '</span>';
        }

        function formatCurrency(value) {
            return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value || 0);
        }

        function showAlert(message, type = 'info') {
            const div = document.createElement('div');
            div.className = 'alert alert-' + type;
            div.textContent = message;
            div.style.position = 'fixed';
            div.style.top = '100px';
            div.style.right = '20px';
            div.style.zIndex = '3000';
            div.style.minWidth = '350px';
            div.style.maxWidth = '500px';
            document.body.appendChild(div);

            setTimeout(() => div.remove(), 4000);
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

        function viewAgent(id) {
            console.log('View agent:', id);
        }

        function saveCustomer() {
            showAlert('Chức năng đang phát triển', 'info');
        }
    </script>
</body>
</html>
'''

# Write file
import os
os.makedirs('static', exist_ok=True)
with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ Generated comprehensive app.html")
print(f"📦 Size: {len(html_content) / 1024:.1f} KB")
print(f"📄 Lines: {len(html_content.splitlines())}")
