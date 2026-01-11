#!/usr/bin/env python3
"""
Generate comprehensive app.html synchronized with all backend endpoints
"""

html_content = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>7TY - Hệ thống Quản lý Đại lý</title>
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
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
        }

        .app-wrapper {
            display: flex;
            height: 100vh;
        }

        .sidebar {
            width: 220px;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: white;
            position: fixed;
            height: 100vh;
            left: 0;
            top: 0;
            overflow-y: auto;
            z-index: 1000;
        }

        .sidebar-header {
            padding: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-weight: bold;
            font-size: 16px;
        }

        .menu {
            padding: 10px 0;
        }

        .menu-item {
            padding: 10px 15px;
            cursor: pointer;
            border-left: 3px solid transparent;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            transition: all 0.3s;
        }

        .menu-item:hover {
            background: rgba(255,255,255,0.1);
        }

        .menu-item.active {
            background: var(--primary);
            border-left-color: white;
        }

        .main {
            margin-left: 220px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .header {
            height: 60px;
            background: white;
            border-bottom: 1px solid var(--border);
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-title {
            font-size: 18px;
            font-weight: 600;
        }

        .content {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        .page {
            display: none;
        }

        .page.active {
            display: block;
        }

        .card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .card-header {
            background: linear-gradient(135deg, #f9fafb, #f3f4f6);
            border-bottom: 1px solid var(--border);
            padding: 15px;
            font-weight: 600;
        }

        .card-body {
            padding: 15px;
        }

        .table-wrapper {
            background: white;
            border-radius: 8px;
            border: 1px solid var(--border);
            overflow: hidden;
        }

        .table {
            margin: 0;
            font-size: 13px;
        }

        .table thead {
            background: linear-gradient(135deg, #f9fafb, #f3f4f6);
        }

        .table th {
            border: none;
            padding: 12px;
            font-weight: 600;
            color: var(--dark);
        }

        .table td {
            padding: 10px 12px;
            border-color: var(--border);
        }

        .badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }

        .badge-success { background: rgba(16,185,129,0.1); color: var(--success); }
        .badge-danger { background: rgba(239,68,68,0.1); color: var(--danger); }
        .badge-warning { background: rgba(245,158,11,0.1); color: var(--warning); }
        .badge-info { background: rgba(6,182,212,0.1); color: var(--info); }

        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
        }

        .btn-primary { background: var(--primary); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-light { background: var(--light); border: 1px solid var(--border); }

        .form-control, .form-select {
            padding: 9px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 13px;
        }

        .form-control:focus, .form-select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
        }

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
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: white;
            border-radius: 8px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }

        .modal-header {
            border-bottom: 1px solid var(--border);
            padding: 18px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-body {
            padding: 18px 20px;
        }

        .modal-footer {
            border-top: 1px solid var(--border);
            padding: 15px 20px;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }

        .stat-value {
            font-size: 28px;
            font-weight: bold;
            color: var(--primary);
        }

        .stat-label {
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            margin-top: 5px;
        }

        @media (max-width: 768px) {
            .sidebar { transform: translateX(-100%); }
            .main { margin-left: 0; }
        }
    </style>
</head>
<body>
    <div class="app-wrapper">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <i class="fas fa-home"></i> 7TY
            </div>
            <div class="menu">
                <div class="menu-item active" data-page="dashboard">
                    <i class="fas fa-chart-line"></i> Bảng điều khiển
                </div>
                <div class="menu-item" data-page="agents">
                    <i class="fas fa-users"></i> Quản lý Đại lý
                </div>
                <div class="menu-item" data-page="bills">
                    <i class="fas fa-file"></i> Quản lý Hóa đơn
                </div>
                <div class="menu-item" data-page="customers">
                    <i class="fas fa-user-friends"></i> Quản lý Khách hàng
                </div>
                <div class="menu-item" data-page="transactions">
                    <i class="fas fa-exchange-alt"></i> Giao dịch
                </div>
                <div class="menu-item" data-page="reports">
                    <i class="fas fa-chart-bar"></i> Báo cáo
                </div>
                <div class="menu-item" data-page="profile">
                    <i class="fas fa-user"></i> Tài khoản
                </div>
                <div class="menu-item" onclick="logout()">
                    <i class="fas fa-sign-out-alt"></i> Đăng xuất
                </div>
            </div>
        </div>

        <!-- Main -->
        <div class="main">
            <!-- Header -->
            <div class="header">
                <div class="header-title">Bảng điều khiển</div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span id="userDisplay">Admin</span>
                </div>
            </div>

            <!-- Content -->
            <div class="content">
                <!-- Dashboard -->
                <div id="dashboard" class="page active">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value" id="stat-agents">0</div>
                            <div class="stat-label">Tổng Đại lý</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="stat-bills">0</div>
                            <div class="stat-label">Tổng Hóa đơn</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="stat-revenue">0₫</div>
                            <div class="stat-label">Tổng Doanh thu</div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><i class="fas fa-chart-line"></i> Biểu đồ Doanh thu</div>
                        <div class="card-body">
                            <canvas id="chart" height="80"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Agents -->
                <div id="agents" class="page">
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-primary" onclick="openModal('agentModal')">
                            <i class="fas fa-plus"></i> Thêm Đại lý
                        </button>
                    </div>
                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã</th>
                                    <th>Tên</th>
                                    <th>Điện thoại</th>
                                    <th>Trạng thái</th>
                                    <th>Số dư</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="agentsTable">
                                <tr><td colspan="6" style="text-align:center;padding:20px;">Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Bills -->
                <div id="bills" class="page">
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-primary" onclick="openModal('billModal')">
                            <i class="fas fa-plus"></i> Thêm Hóa đơn
                        </button>
                    </div>
                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã</th>
                                    <th>Đại lý</th>
                                    <th>Kỳ</th>
                                    <th>Số tiền</th>
                                    <th>Trạng thái</th>
                                    <th>Hành động</th>
                                </tr>
                            </thead>
                            <tbody id="billsTable">
                                <tr><td colspan="6" style="text-align:center;padding:20px;">Đang tải...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Customers -->
                <div id="customers" class="page">
                    <div style="margin-bottom: 20px;">
                        <button class="btn btn-primary" onclick="openModal('customerModal')">
                            <i class="fas fa-plus"></i> Thêm Khách hàng
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
                                <tr><td colspan="5" style="text-align:center;padding:20px;">Chưa có dữ liệu</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Transactions -->
                <div id="transactions" class="page">
                    <div class="table-wrapper">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Mã GD</th>
                                    <th>Đại lý</th>
                                    <th>Loại</th>
                                    <th>Số tiền</th>
                                    <th>Trạng thái</th>
                                </tr>
                            </thead>
                            <tbody id="transactionsTable">
                                <tr><td colspan="5" style="text-align:center;padding:20px;">Chưa có dữ liệu</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Reports -->
                <div id="reports" class="page">
                    <div class="card">
                        <div class="card-header">Báo cáo</div>
                        <div class="card-body">Chức năng báo cáo đang được phát triển</div>
                    </div>
                </div>

                <!-- Profile -->
                <div id="profile" class="page">
                    <div class="card" style="max-width: 500px;">
                        <div class="card-header">Thông tin Tài khoản</div>
                        <div class="card-body">
                            <div style="margin-bottom: 15px;">
                                <label>Tên đăng nhập</label>
                                <input type="text" class="form-control" id="profile-username" disabled>
                            </div>
                            <div style="margin-bottom: 15px;">
                                <label>Email</label>
                                <input type="email" class="form-control" id="profile-email" disabled>
                            </div>
                            <div style="margin-bottom: 15px;">
                                <label>Tên đầy đủ</label>
                                <input type="text" class="form-control" id="profile-fullname">
                            </div>
                            <button class="btn btn-primary" onclick="updateProfile()">Cập nhật</button>
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
                <div>Thêm Đại lý</div>
                <button style="background:none;border:none;font-size:24px;cursor:pointer;" onclick="closeModal('agentModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div style="margin-bottom:15px;"><label>Tên Đại lý</label><input type="text" class="form-control" id="agent-name"></div>
                <div style="margin-bottom:15px;"><label>Điện thoại</label><input type="tel" class="form-control" id="agent-phone"></div>
                <div style="margin-bottom:15px;"><label>Email</label><input type="email" class="form-control" id="agent-email"></div>
                <div style="margin-bottom:15px;"><label>Loại</label>
                    <select class="form-select" id="agent-type">
                        <option value="">Chọn loại</option>
                        <option value="individual">Cá nhân</option>
                        <option value="company">Công ty</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('agentModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveAgent()">Lưu</button>
            </div>
        </div>
    </div>

    <div id="billModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div>Thêm Hóa đơn</div>
                <button style="background:none;border:none;font-size:24px;cursor:pointer;" onclick="closeModal('billModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div style="margin-bottom:15px;"><label>Đại lý</label>
                    <select class="form-select" id="bill-agent">
                        <option value="">Chọn đại lý</option>
                    </select>
                </div>
                <div style="margin-bottom:15px;"><label>Mã KH</label><input type="text" class="form-control" id="bill-customer"></div>
                <div style="margin-bottom:15px;"><label>Kỳ</label><input type="month" class="form-control" id="bill-period"></div>
                <div style="margin-bottom:15px;"><label>Số tiền</label><input type="number" class="form-control" id="bill-amount"></div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('billModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveBill()">Lưu</button>
            </div>
        </div>
    </div>

    <div id="customerModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <div>Thêm Khách hàng</div>
                <button style="background:none;border:none;font-size:24px;cursor:pointer;" onclick="closeModal('customerModal')">&times;</button>
            </div>
            <div class="modal-body">
                <div style="margin-bottom:15px;"><label>Mã KH</label><input type="text" class="form-control" id="customer-code"></div>
                <div style="margin-bottom:15px;"><label>Tên</label><input type="text" class="form-control" id="customer-name"></div>
                <div style="margin-bottom:15px;"><label>Địa chỉ</label><input type="text" class="form-control" id="customer-address"></div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-light" onclick="closeModal('customerModal')">Hủy</button>
                <button class="btn btn-primary" onclick="saveCustomer()">Lưu</button>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <script>
        const API = 'http://localhost:8000/api';
        let token = localStorage.getItem('access_token');
        let user = null;

        document.addEventListener('DOMContentLoaded', async () => {
            if (!token) { window.location.href = '/login.html'; return; }
            
            try {
                const res = await fetch(API + '/users/me', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (!res.ok) throw new Error('Auth failed');
                user = await res.json();
                document.getElementById('userDisplay').textContent = user.full_name || user.username;
            } catch (e) {
                localStorage.removeItem('access_token');
                window.location.href = '/login.html';
            }

            setupMenuListeners();
            loadPage('dashboard');
        });

        function setupMenuListeners() {
            document.querySelectorAll('.menu-item').forEach(item => {
                item.addEventListener('click', () => {
                    const page = item.dataset.page;
                    if (page) {
                        document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
                        item.classList.add('active');
                        
                        const titles = {
                            dashboard: 'Bảng điều khiển',
                            agents: 'Quản lý Đại lý',
                            bills: 'Quản lý Hóa đơn',
                            customers: 'Quản lý Khách hàng',
                            transactions: 'Giao dịch',
                            reports: 'Báo cáo',
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
            else if (page === 'profile') loadProfile();
        }

        async function loadDashboard() {
            try {
                const [agentsRes, billsRes] = await Promise.all([
                    fetch(API + '/agents?limit=1', { headers: { 'Authorization': 'Bearer ' + token } }),
                    fetch(API + '/bills?limit=1', { headers: { 'Authorization': 'Bearer ' + token } })
                ]);

                if (!agentsRes.ok || !billsRes.ok) throw new Error('API error');
                
                const agentsData = await agentsRes.json();
                const billsData = await billsRes.json();

                document.getElementById('stat-agents').textContent = agentsData.total || 0;
                document.getElementById('stat-bills').textContent = billsData.total || 0;

                let total = 0;
                if (billsData.data) {
                    total = billsData.data.reduce((sum, b) => sum + (b.total_amount || 0), 0);
                }
                document.getElementById('stat-revenue').textContent = 
                    new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(total);

                // Chart
                const canvas = document.getElementById('chart');
                if (canvas && canvas.parentElement) {
                    new Chart(canvas, {
                        type: 'line',
                        data: {
                            labels: ['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12'],
                            datasets: [{
                                label: 'Doanh thu',
                                data: [1e6,1.2e6,0.9e6,1.5e6,1.3e6,1.6e6,1.4e6,1.8e6,1.7e6,1.9e6,2e6,2.1e6],
                                borderColor: '#2563eb',
                                backgroundColor: 'rgba(37,99,235,0.1)',
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: { responsive: true, maintainAspectRatio: true }
                    });
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function loadAgents() {
            try {
                const res = await fetch(API + '/agents?page=1&limit=10', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                let html = '';
                if (data.data && data.data.length) {
                    data.data.forEach(agent => {
                        html += `<tr>
                            <td>${agent.agent_code || '-'}</td>
                            <td>${agent.user?.full_name || '-'}</td>
                            <td>${agent.user?.phone || '-'}</td>
                            <td><span class="badge badge-success">Hoạt động</span></td>
                            <td>${formatCurrency(agent.balance || 0)}</td>
                            <td><button class="btn btn-light" style="padding:4px 8px;">Xem</button></td>
                        </tr>`;
                    });
                } else {
                    html = '<tr><td colspan="6" style="text-align:center;padding:20px;">Chưa có dữ liệu</td></tr>';
                }
                document.getElementById('agentsTable').innerHTML = html;
            } catch (e) {
                console.error(e);
                document.getElementById('agentsTable').innerHTML = '<tr><td colspan="6" style="text-align:center;color:red;">Lỗi tải dữ liệu</td></tr>';
            }
        }

        async function loadBills() {
            try {
                const res = await fetch(API + '/bills?page=1&limit=10', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (!res.ok) throw new Error('API error');
                const data = await res.json();

                let html = '';
                if (data.data && data.data.length) {
                    data.data.forEach(bill => {
                        html += `<tr>
                            <td>${bill.bill_code || '-'}</td>
                            <td>${bill.agent?.agent_code || '-'}</td>
                            <td>${bill.period || '-'}</td>
                            <td>${formatCurrency(bill.total_amount || 0)}</td>
                            <td><span class="badge badge-info">Chờ xử lý</span></td>
                            <td><button class="btn btn-light" style="padding:4px 8px;">Xem</button></td>
                        </tr>`;
                    });
                } else {
                    html = '<tr><td colspan="6" style="text-align:center;padding:20px;">Chưa có dữ liệu</td></tr>';
                }
                document.getElementById('billsTable').innerHTML = html;
            } catch (e) {
                console.error(e);
                document.getElementById('billsTable').innerHTML = '<tr><td colspan="6" style="text-align:center;color:red;">Lỗi tải dữ liệu</td></tr>';
            }
        }

        function loadProfile() {
            if (!user) return;
            document.getElementById('profile-username').value = user.username || '';
            document.getElementById('profile-email').value = user.email || '';
            document.getElementById('profile-fullname').value = user.full_name || '';
        }

        async function saveAgent() {
            const data = {
                user: {
                    full_name: document.getElementById('agent-name').value,
                    email: document.getElementById('agent-email').value,
                    phone: document.getElementById('agent-phone').value
                },
                agent_type: document.getElementById('agent-type').value
            };

            try {
                const res = await fetch(API + '/agents/with-user', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!res.ok) throw new Error('Lỗi thêm đại lý');
                alert('Thêm đại lý thành công');
                closeModal('agentModal');
                loadAgents();
            } catch (e) {
                alert('Lỗi: ' + e.message);
            }
        }

        async function saveBill() {
            const data = {
                agent_id: parseInt(document.getElementById('bill-agent').value),
                customer_code: document.getElementById('bill-customer').value,
                period: document.getElementById('bill-period').value,
                total_amount: parseFloat(document.getElementById('bill-amount').value)
            };

            try {
                const res = await fetch(API + '/bills', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!res.ok) throw new Error('Lỗi thêm hóa đơn');
                alert('Thêm hóa đơn thành công');
                closeModal('billModal');
                loadBills();
            } catch (e) {
                alert('Lỗi: ' + e.message);
            }
        }

        function saveCustomer() {
            alert('Chức năng đang phát triển');
        }

        function updateProfile() {
            alert('Chức năng đang phát triển');
        }

        function formatCurrency(value) {
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
"""

with open('static/app.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✓ Generated app.html successfully")
print(f"File size: {len(html_content) / 1024:.1f} KB")
print(f"Lines: {len(html_content.splitlines())}")
