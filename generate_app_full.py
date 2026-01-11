#!/usr/bin/env python3
import pathlib

root = pathlib.Path(__file__).resolve().parent

html_main = r'''<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>7TY.VN - Hệ thống quản trị</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>
    :root { --primary:#2563eb; --success:#10b981; --danger:#ef4444; --warning:#f59e0b; --info:#06b6d4; --muted:#6b7280; --border:#e5e7eb; --bg:#f8fafc; --dark:#0f172a; }
    *{box-sizing:border-box;} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:var(--bg);color:var(--dark);} a{text-decoration:none;}
    .layout{display:flex;min-height:100vh;} .sidebar{width:270px;background:linear-gradient(180deg,#0b1221 0%,#111827 100%);color:#e5e7eb;position:fixed;top:0;bottom:0;left:0;overflow:auto;padding:16px 12px;}
    .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;padding:10px;} .menu-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;color:#e5e7eb;cursor:pointer;} .menu-item:hover{background:rgba(37,99,235,0.15);} .menu-item.active{background:rgba(37,99,235,0.2);} .section-label{color:#94a3b8;font-size:12px;padding:6px 12px;}
    .content{margin-left:270px;flex:1;display:flex;flex-direction:column;} .topbar{height:64px;background:#fff;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 18px;position:sticky;top:0;z-index:5;}
    .main{padding:18px;} .page{display:none;} .page.active{display:block;} .card{border:1px solid var(--border);border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:16px;} .card-header{background:linear-gradient(135deg,#f8fafc,#eef2ff);border-bottom:1px solid var(--border);padding:14px 16px;font-weight:600;} .card-body{padding:14px 16px;}
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;} .stat{padding:14px;border-radius:12px;background:#fff;border:1px solid var(--border);} .stat .label{font-size:12px;color:var(--muted);} .stat .value{font-size:24px;font-weight:700;margin-top:6px;}
    table{width:100%;} thead{background:#f8fafc;} th,td{padding:10px;font-size:13px;border-bottom:1px solid var(--border);} th{font-weight:600;color:#475569;white-space:nowrap;}
    .badge-success{background:rgba(16,185,129,.12);color:#047857;} .badge-warning{background:rgba(245,158,11,.15);color:#b45309;} .badge-danger{background:rgba(239,68,68,.12);color:#b91c1c;} .badge-info{background:rgba(6,182,212,.12);color:#0e7490;}
    .modal-backdrop-custom{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;align-items:center;justify-content:center;z-index:999;} .modal-backdrop-custom.active{display:flex;} .modal-panel{width:min(960px,94vw);background:#fff;border-radius:12px;box-shadow:0 24px 60px rgba(0,0,0,.25);max-height:90vh;overflow:auto;} .modal-header,.modal-footer{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;} .modal-footer{border-top:1px solid var(--border);border-bottom:none;} .modal-body{padding:14px 16px;}
    .grid{display:grid;gap:12px;} .grid-2{grid-template-columns:repeat(auto-fit,minmax(240px,1fr));} .grid-3{grid-template-columns:repeat(auto-fit,minmax(200px,1fr));}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand"><i class="fas fa-bolt text-warning"></i><span>7TY.VN</span></div>
      <div class="menu">
        <div class="section-label">Tổng quan</div>
        <div class="menu-item active" data-page="dashboard"><i class="fas fa-chart-line"></i><span>Dashboard</span></div>
        <div class="menu-item" data-page="reports"><i class="fas fa-chart-bar"></i><span>Báo cáo</span></div>
        <div class="section-label">Nghiệp vụ</div>
        <div class="menu-item" data-page="agents"><i class="fas fa-users"></i><span>Đại lý</span></div>
        <div class="menu-item" data-page="bills"><i class="fas fa-file-invoice"></i><span>Hóa đơn</span></div>
        <div class="menu-item" data-page="customers"><i class="fas fa-user-tie"></i><span>Khách hàng</span></div>
        <div class="menu-item" data-page="transactions"><i class="fas fa-exchange-alt"></i><span>Giao dịch</span></div>
        <div class="menu-item" data-page="notifications"><i class="fas fa-bell"></i><span>Thông báo</span></div>
        <div class="section-label">Quản trị</div>
        <div class="menu-item" data-page="users"><i class="fas fa-user-shield"></i><span>Người dùng</span></div>
        <div class="menu-item" data-page="system"><i class="fas fa-sliders-h"></i><span>Cấu hình</span></div>
        <div class="menu-item" data-page="logs"><i class="fas fa-scroll"></i><span>Nhật ký</span></div>
        <div class="menu-item" data-page="api"><i class="fas fa-plug"></i><span>External API</span></div>
      </div>
    </aside>
    <div class="content">
      <div class="topbar">
        <div id="pageTitle" class="fw-semibold">Dashboard</div>
        <div class="d-flex align-items-center gap-2">
          <span class="badge bg-primary" id="userRole">role</span>
          <span id="userDisplay" class="fw-semibold">---</span>
          <button class="btn btn-outline-secondary btn-sm" onclick="logout()"><i class="fas fa-sign-out-alt"></i> Đăng xuất</button>
        </div>
      </div>
      <main class="main">
        <section id="page-dashboard" class="page active">
          <div class="stats">
            <div class="stat"><div class="label">Tổng Đại lý</div><div class="value" id="statAgents">0</div></div>
            <div class="stat"><div class="label">Tổng Hóa đơn</div><div class="value" id="statBills">0</div></div>
            <div class="stat"><div class="label">Doanh thu</div><div class="value" id="statRevenue">0₫</div></div>
            <div class="stat"><div class="label">Khách hàng</div><div class="value" id="statCustomers">0</div></div>
          </div>
          <div class="card"><div class="card-header"><i class="fas fa-chart-area me-2"></i>Doanh thu 12 tháng</div><div class="card-body" style="height:360px"><canvas id="chartRevenue"></canvas></div></div>
        </section>

        <!-- ENTITY PAGES PLACEHOLDER -->

        <section id="page-reports" class="page">
          <div class="card"><div class="card-header"><i class="fas fa-chart-pie me-2"></i>Báo cáo</div><div class="card-body">
            <div class="grid grid-3 mb-3">
              <div><label class="form-label">Khoảng thời gian</label><input type="month" id="report-period" class="form-control form-control-sm"></div>
              <div><label class="form-label">Loại báo cáo</label><select id="report-type" class="form-select form-select-sm"><option value="sales">Doanh thu</option><option value="agents">Hiệu suất đại lý</option><option value="bills">Tình trạng hóa đơn</option><option value="customers">Khách hàng</option></select></div>
              <div class="d-flex align-items-end"><button class="btn btn-primary btn-sm" onclick="runReport()"><i class="fas fa-play"></i> Tạo báo cáo</button></div>
            </div>
            <div id="report-result" class="border rounded p-3 bg-white">Chưa có dữ liệu</div>
          </div></div>
        </section>

        <!-- MODALS PLACEHOLDER -->

      </main>
    </div>
  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
  <script>
    const API = `${window.location.origin}/api`;
    let token = localStorage.getItem("access_token") || localStorage.getItem("token");
    let currentUser = null;
    const pageMap = {dashboard:"Dashboard",reports:"Báo cáo",agents:"Đại lý",bills:"Hóa đơn",customers:"Khách hàng",transactions:"Giao dịch",notifications:"Thông báo",users:"Người dùng",system:"Cấu hình",logs:"Nhật ký",api:"External API"};

    document.addEventListener("DOMContentLoaded", initApp);
    function initApp(){ if(!token){ window.location.href="/login.html"; return;} bindMenu(); fetchMe(); }
    function bindMenu(){ document.querySelectorAll(".menu-item").forEach(it=>{ it.addEventListener("click",()=>{ const p=it.dataset.page; switchPage(p); }); }); }
    function switchPage(p){ document.querySelectorAll(".menu-item").forEach(i=>i.classList.toggle("active", i.dataset.page===p)); document.querySelectorAll(".page").forEach(pg=>pg.classList.remove("active")); const el=document.getElementById(`page-${p}`); if(el) el.classList.add("active"); document.getElementById("pageTitle").textContent = pageMap[p]||p; loadPageData(p); }
    async function fetchMe(){ try{ const res=await fetch(`${API}/users/me`,{headers:{Authorization:`Bearer ${token}`}}); if(res.status===401) throw new Error("unauth"); if(!res.ok) throw new Error(await res.text()); currentUser=await res.json(); document.getElementById("userDisplay").textContent=currentUser.full_name||currentUser.username; document.getElementById("userRole").textContent=currentUser.role||"user"; loadPageData("dashboard"); }catch(e){ logout(); }}
    function authHeaders(){ return {Authorization:`Bearer ${token}`,"Content-Type":"application/json"}; }

    async function loadPageData(p){ const map={dashboard:loadDashboard,agents:()=>loadList("agents"),bills:()=>loadList("bills"),customers:()=>loadList("customers"),transactions:()=>loadList("transactions"),notifications:()=>loadList("notifications"),users:()=>loadList("users"),system:()=>loadList("system"),logs:()=>loadList("logs"),api:renderApiDocs,reports:()=>{}}; if(map[p]) map[p](); }

    async function loadDashboard(){ try{ const res=await fetch(`${API}/system/dashboard`,{headers:authHeaders()}); if(res.status===401) return logout(); if(!res.ok) throw new Error(await res.text()); const d=await res.json(); const stats=d.stats||d; document.getElementById("statAgents").textContent=stats.total_agents||0; document.getElementById("statBills").textContent=stats.total_bills||0; document.getElementById("statCustomers").textContent=stats.total_customers||0; document.getElementById("statRevenue").textContent=new Intl.NumberFormat("vi-VN",{style:"currency",currency:"VND"}).format(stats.today_revenue||stats.total_revenue||0); if(d.sales_data) renderRevenueChart(d.sales_data); }catch(e){ console.error(e);} }
    let revenueChart=null; function renderRevenueChart(series){ const ctx=document.getElementById("chartRevenue"); if(!ctx) return; if(revenueChart) revenueChart.destroy(); const labels=(Array.isArray(series)?series.map(i=>i.date||i.period):Object.keys(series)); const values=(Array.isArray(series)?series.map(i=>i.amount||i.total_amount||0):Object.values(series)); revenueChart=new Chart(ctx,{type:"line",data:{labels,datasets:[{label:"Doanh thu",data:values,fill:true,borderColor:"#2563eb",backgroundColor:"rgba(37,99,235,0.12)",tension:0.35}]},options:{plugins:{legend:{display:false}}}}); }

    const entityConfig={
      agents:{path:"/agents"},
      bills:{path:"/bills"},
      customers:{path:"/customers"},
      transactions:{path:"/transactions"},
      notifications:{path:"/notifications"},
      users:{path:"/users"},
      system:{path:"/system/config"},
      logs:{path:"/system/logs"},
      api:{path:"/v1"}
    };

    function extractList(eid,d){ if(!d) return []; if(Array.isArray(d)) return d; if(eid==="users") return d.users||d.data||d.items||[]; if(eid==="logs") return d.logs||d.data||d.items||[]; return d.data||d.items||d.results||d.records||[]; }
    function extractTotal(d){ return d?.total||d?.count||d?.pagination?.total||0; }
    function extractPage(d){ return d?.page||d?.pagination?.page||1; }
    function extractLimit(d){ return d?.limit||d?.pagination?.limit||10; }
    function extractPages(d, limit){ return d?.pages||d?.total_pages||Math.max(1, Math.ceil((extractTotal(d)||0)/(limit||10))); }

    function buildListUrl(eid,page,limit){ const cfg=entityConfig[eid]; if(!cfg) return ''; let base=`${API}${cfg.path}`; const useSkip = (eid==='customers' || eid==='transactions'); const q = []; if(useSkip){ q.push(`skip=${(page-1)*limit}`); q.push(`limit=${limit}`); } else { q.push(`page=${page}`); q.push(`limit=${limit}`); } const s=document.getElementById(`${eid}-search`); if(s&&s.value) q.push(`search=${encodeURIComponent(s.value)}`); const st=document.getElementById(`${eid}-status`); if(st&&st.value) q.push(`status=${st.value}`); return base + (base.includes('?')?'&':'?') + q.join('&'); }

    async function loadList(eid,page=1){ const limit=10; const url=buildListUrl(eid,page,limit); if(!url) return; const tb=document.getElementById(`${eid}-table`); tb.innerHTML='<tr><td colspan="20" class="text-center"><div class="spinner-border spinner-border-sm text-primary"></div></td></tr>'; try{ const res=await fetch(url,{headers:authHeaders()}); if(res.status===401) return logout(); if(!res.ok) throw new Error(await res.text()); const d=await res.json(); const rows=extractList(eid,d); renderTable(eid,rows); renderPagination(eid,d,page,limit); }catch(err){ tb.innerHTML=`<tr><td colspan="20" class="text-danger">${err}</td></tr>`; }}

    function renderTable(eid,rows){ const tb=document.getElementById(`${eid}-table`); if(!rows||rows.length===0){ tb.innerHTML=`<tr><td colspan="20" class="text-center text-muted py-3">Chưa có dữ liệu</td></tr>`; return; } const map={
      agents:r=>`<tr><td>${r.agent_code||""}</td><td>${r.agent_name||r.user?.full_name||""}</td><td>${r.agent_type||""}</td><td>${badge(r.status)}</td><td>${money(r.balance)}</td><td>${fmtDate(r.created_at)}</td><td>${actions("agents",r.id)}</td></tr>`,
      bills:r=>`<tr><td>${r.bill_code||""}</td><td>${r.agent?.agent_code||""}</td><td>${r.customer_code||r.customer?.customer_code||""}</td><td>${r.period||""}</td><td>${money(r.total_amount||r.amount)}</td><td>${badge(r.status)}</td><td>${r.payment_method||""}</td><td>${actions("bills",r.id)}</td></tr>`,
      customers:r=>`<tr><td>${r.customer_code||""}</td><td>${r.customer_name||r.full_name||""}</td><td>${r.phone||""}</td><td>${r.address||""}</td><td>${badge(r.status)}</td><td>${r.agent?.agent_code||""}</td><td>${actions("customers",r.id)}</td></tr>`,
      transactions:r=>`<tr><td>${r.transaction_code||""}</td><td>${r.agent?.agent_code||""}</td><td>${r.transaction_type||""}</td><td>${money(r.amount)}</td><td>${badge(r.status)}</td><td>${fmtDate(r.created_at)}</td><td>${actions("transactions",r.id)}</td></tr>`,
      notifications:r=>`<tr><td>${r.title||""}</td><td>${r.message||""}</td><td>${r.notification_type||r.level||"info"}</td><td>${badge(r.status||r.notification_status)}</td><td>${fmtDate(r.created_at)}</td><td>${actions("notifications",r.id)}</td></tr>`,
      users:r=>`<tr><td>${r.username||""}</td><td>${r.full_name||""}</td><td>${r.email||""}</td><td>${r.role||""}</td><td>${badge(r.is_active?"active":"inactive")}</td><td>${fmtDate(r.last_login)}</td><td>${actions("users",r.id)}</td></tr>`,
      system:r=>`<tr><td>${r.key||""}</td><td>${r.value||""}</td><td>${r.description||""}</td><td>${r.updated_by||""}</td><td>${fmtDate(r.updated_at)}</td><td>${actions("system",r.id)}</td></tr>`,
      logs:r=>`<tr><td>${fmtDate(r.created_at)}</td><td>${r.user||r.user_id||""}</td><td>${r.action||r.activity_type||""}</td><td>${r.description||r.details||""}</td><td>${r.ip_address||r.ip||""}</td><td>${badge(r.status||"info")}</td></tr>`,
      api:r=>`<tr><td>${r.path||""}</td><td>${r.method||""}</td><td>${r.description||""}</td><td>${r.auth||""}</td><td>${r.rate_limit||""}</td><td><button class="btn btn-sm btn-outline-primary" onclick="copyText('${r.path||""}')">Copy</button></td></tr>`
    }; const fn=map[eid]|| (r=>`<tr><td>${JSON.stringify(r)}</td></tr>`); tb.innerHTML = rows.map(fn).join(""); }

    function renderPagination(eid,d,page,limit){ const ul=document.getElementById(`${eid}-pagination`); if(!ul) return; const pages=extractPages(d,limit); let html=""; for(let i=1;i<=pages&&i<=10;i++){ const active=i===page?"active":""; html += `<li class="page-item ${active}"><button class="page-link" onclick="loadList('${eid}',${i})">${i}</button></li>`; } ul.innerHTML=html; }
    function badge(st){ const map={active:"success",completed:"success",paid:"success",sold:"info",pending:"warning",suspended:"danger",failed:"danger",cancelled:"danger",deleted:"danger",inactive:"warning"}; const cls=map[st]||"info"; return `<span class="badge badge-${cls}">${st||"--"}</span>`; }
    function money(v){ return new Intl.NumberFormat("vi-VN",{style:"currency",currency:"VND"}).format(v||0); }
    function fmtDate(d){ if(!d) return ""; try{return new Date(d).toLocaleString("vi-VN");}catch(e){return d;} }
    function openModal(id){ const el=document.getElementById(id); if(el) el.classList.add("active"); }
    function closeModal(id){ const el=document.getElementById(id); if(el) el.classList.remove("active"); }
    async function saveEntity(eid){ const cfg=entityConfig[eid]; if(!cfg) return; const body={}; document.querySelectorAll(`#${eid}-modal input, #${eid}-modal select, #${eid}-modal textarea`).forEach(inp=>{ body[inp.name||inp.id]=inp.value; }); try{ const res=await fetch(`${API}${cfg.path}`,{method:"POST",headers:authHeaders(),body:JSON.stringify(body)}); if(res.status===401) return logout(); if(!res.ok) throw new Error(await res.text()); closeModal(`${eid}-modal`); loadList(eid); }catch(err){ alert("Lỗi: "+err); }}
    function refreshPage(){ location.reload(); }
    function logout(){ localStorage.removeItem("access_token"); window.location.href="/login.html"; }
    function debounceFilter(eid){ clearTimeout(window.__db); window.__db=setTimeout(()=>applyFilter(eid),400); }
    function applyFilter(eid){ loadList(eid,1); }
    function actions(eid,id){ return `<div class="btn-group btn-group-sm"><button class="btn btn-light" onclick="editEntity('${eid}',${id})"><i class="fas fa-edit"></i></button><button class="btn btn-danger" onclick="deleteEntity('${eid}',${id})"><i class="fas fa-trash"></i></button></div>`; }
    function editEntity(eid,id){ alert(`Edit ${eid} ${id}`); }
    async function deleteEntity(eid,id){ if(!confirm("Xóa mục này?")) return; const cfg=entityConfig[eid]; if(!cfg) return; const res=await fetch(`${API}${cfg.path}/${id}`,{method:"DELETE",headers:authHeaders()}); if(res.status===401) return logout(); if(res.ok) loadList(eid); else alert("Lỗi xóa"); }
    function copyText(t){ navigator.clipboard.writeText(t); }
    function renderApiDocs(){ const tb=document.getElementById("api-table"); if(!tb) return; tb.innerHTML = apiEndpoints.map(ep=>`<tr><td>${ep.path}</td><td>${ep.method}</td><td>${ep.desc}</td><td>${ep.auth}</td><td>${ep.rate}</td><td><button class="btn btn-sm btn-outline-primary" onclick="copyText('${ep.path}')">Copy</button></td></tr>`).join(''); }
    async function runReport(){ const m=document.getElementById("report-period").value; const type=document.getElementById("report-type").value||"sales"; const box=document.getElementById("report-result"); const range=monthRange(m); const payload={report_type:type,start_date:range.start,end_date:range.end,group_by:"month"}; box.innerHTML='<div class="text-center"><div class="spinner-border spinner-border-sm text-primary"></div> Đang tạo báo cáo...</div>'; try{ const res=await fetch(`${API}/system/reports/sales`,{method:"POST",headers:authHeaders(),body:JSON.stringify(payload)}); if(res.status===401) return logout(); if(!res.ok) throw new Error(await res.text()); const data=await res.json(); box.innerHTML=`<pre class="mb-0" style="white-space:pre-wrap;">${JSON.stringify(data,null,2)}</pre>`; }catch(err){ box.innerHTML=`<div class="text-danger">${err}</div>`; }}
    function monthRange(m){ if(!m) { const now=new Date(); const start=new Date(now.getFullYear(), now.getMonth(),1); const end=new Date(now.getFullYear(), now.getMonth()+1,0); return {start:start.toISOString(), end:end.toISOString()}; } const [y,mon]=m.split('-'); const start=new Date(parseInt(y,10), parseInt(mon,10)-1,1); const end=new Date(parseInt(y,10), parseInt(mon,10),0); return {start:start.toISOString(), end:end.toISOString()}; }

    const apiEndpoints = [];
  </script>
</body>
</html>
'''

# Entity page templates
entity_blocks = []
entities = [
    ('agents','Quản lý Đại lý',['Mã','Tên','Loại','Trạng thái','Số dư','Ngày tạo','Hành động']),
    ('bills','Quản lý Hóa đơn',['Mã HĐ','Đại lý','Khách hàng','Kỳ','Số tiền','Trạng thái','Thanh toán','Hành động']),
    ('customers','Quản lý Khách hàng',['Mã KH','Tên','SĐT','Địa chỉ','Trạng thái','Đại lý','Hành động']),
    ('transactions','Giao dịch',['Mã GD','Đại lý','Loại','Số tiền','Trạng thái','Ngày','Hành động']),
    ('notifications','Thông báo',['Tiêu đề','Nội dung','Mức độ','Trạng thái','Thời gian','Hành động']),
    ('users','Người dùng',['Username','Họ tên','Email','Vai trò','Trạng thái','Lần đăng nhập','Hành động']),
    ('system','Cấu hình hệ thống',['Khóa','Giá trị','Mô tả','Cập nhật bởi','Cập nhật lúc','Hành động']),
    ('logs','Nhật ký',['Thời gian','User','Hành động','Mô tả','IP','Kết quả']),
    ('api','External API',['Endpoint','Method','Mô tả','Auth','Tần suất','Hành động'])
]
for eid,title,cols in entities:
    header = f"<section id=\"page-{eid}\" class=\"page\"><div class=\"d-flex justify-content-between align-items-center mb-3\"><h5 class=\"mb-0\">{title}</h5><div class=\"d-flex gap-2\"><button class=\"btn btn-light btn-sm\" onclick=\"refreshPage()\"><i class=\\\"fas fa-rotate\\\"></i> Làm mới</button><button class=\"btn btn-primary btn-sm\" onclick=\"openModal(''{eid}-modal'')\"><i class=\\\"fas fa-plus\\\"></i> Thêm mới</button></div></div>"
    filters = f"<div class=\"card\"><div class=\"card-body\"><div class=\"grid grid-3 mb-3\"><div><label class=\"form-label\">Tìm kiếm</label><input id=\"{eid}-search\" class=\"form-control form-control-sm\" placeholder=\"Nhập từ khóa\" oninput=\"debounceFilter(''{eid}'')\"></div><div><label class=\"form-label\">Trạng thái</label><select id=\"{eid}-status\" class=\"form-select form-select-sm\" onchange=\"applyFilter(''{eid}'')\"><option value=\"\">Tất cả</option><option value=\"active\">Hoạt động</option><option value=\"pending\">Chờ duyệt</option><option value=\"suspended\">Tạm khóa</option><option value=\"deleted\">Đã xóa</option></select></div><div><label class=\"form-label\">Khoảng thời gian</label><input type=\"month\" id=\"{eid}-period\" class=\"form-control form-control-sm\" onchange=\"applyFilter(''{eid}'')\"></div></div>"
    table_head = "".join([f"<th>{c}</th>" for c in cols])
    table = f"<div class=\\\"table-responsive\\\"><table class=\\\"table align-middle\\\"><thead><tr>{table_head}</tr></thead><tbody id=\\\"{eid}-table\\\"><tr><td colspan=\\\"20\\\" class=\\\"text-center py-3 text-muted\\\">Đang tải...</td></tr></tbody></table></div><nav class=\\\"mt-2\\\"><ul class=\\\"pagination pagination-sm mb-0\\\" id=\\\"{eid}-pagination\\\"></ul></nav></div></div></section>"
    entity_blocks.append(header + filters + table)

entities_html = "\n".join(entity_blocks)
html_main = html_main.replace('<!-- ENTITY PAGES PLACEHOLDER -->', entities_html)

# Modals
modal_fields = {
    'agents':['Tên','Email','Điện thoại','Loại','Mật khẩu'],
    'bills':['Mã KH','Kỳ','Số tiền','Đại lý','Hạn thanh toán'],
    'customers':['Mã KH','Tên','SĐT','Địa chỉ','Email'],
    'transactions':['Loại','Số tiền','Mã HĐ','Ghi chú'],
    'users':['Username','Email','Họ tên','Vai trò','Mật khẩu'],
    'system':['Khóa','Giá trị','Mô tả'],
    'notifications':['Tiêu đề','Nội dung','Mức độ']
}
modal_html_blocks = []
for k, fields in modal_fields.items():
    inputs = "".join([f"<div><label class=\\\"form-label\\\">{f}</label><input id=\\\"{k}-field-{idx}\\\" class=\\\"form-control\\\" placeholder=\\\"{f}\\\"></div>" for idx,f in enumerate(fields)])
    modal_html_blocks.append(f"<div id=\\\"{k}-modal\\\" class=\\\"modal-backdrop-custom\\\"><div class=\\\"modal-panel\\\"><div class=\\\"modal-header\\\"><span>Thêm {k}</span><button class=\\\"btn btn-sm btn-outline-secondary\\\" onclick=\\\"closeModal(''{k}-modal'')\\\">Đóng</button></div><div class=\\\"modal-body\\\"><div class=\\\"grid grid-2\\\">{inputs}</div></div><div class=\\\"modal-footer\\\"><button class=\\\"btn btn-light\\\" onclick=\\\"closeModal(this.closest(''.modal-backdrop-custom'').id)\\\">Hủy</button><button class=\\\"btn btn-primary\\\" onclick=\\\"saveEntity(''{k}'')\\\"><i class=\\\"fas fa-save\\\"></i> Lưu</button></div></div></div>")
modal_html = "\n".join(modal_html_blocks)
html_main = html_main.replace('<!-- MODALS PLACEHOLDER -->', modal_html)

# API endpoints filler (not exhaustive but representative)
api_endpoints = [
    {"path":"/api/auth/login","method":"POST","desc":"Đăng nhập","auth":"No","rate":"RL"},
    {"path":"/api/auth/refresh","method":"POST","desc":"Refresh","auth":"No","rate":"RL"},
    {"path":"/api/auth/logout","method":"POST","desc":"Đăng xuất","auth":"Bearer","rate":""},
]
for i in range(1,40):
  api_endpoints.append({"path":f"/api/agents/{i}","method":"GET","desc":"Agent detail","auth":"Bearer","rate":""})
for i in range(1,40):
  api_endpoints.append({"path":f"/api/bills/{i}","method":"GET","desc":"Bill detail","auth":"Bearer","rate":""})
for i in range(1,40):
  api_endpoints.append({"path":f"/api/customers/{i}","method":"GET","desc":"Customer detail","auth":"Bearer","rate":""})
for i in range(1,40):
  api_endpoints.append({"path":f"/api/transactions/{i}","method":"GET","desc":"Transaction detail","auth":"Bearer","rate":""})
for i in range(1,40):
  api_endpoints.append({"path":f"/api/notifications/{i}","method":"PUT","desc":"Mark read","auth":"Bearer","rate":""})
api_js = "\n".join([f"    apiEndpoints.push({{path:'{ep['path']}',method:'{ep['method']}',desc:'{ep['desc']}',auth:'{ep['auth']}',rate:'{ep['rate']}'}});" for ep in api_endpoints])
html_main = html_main.replace('const apiEndpoints = [];', f'const apiEndpoints = [];\n{api_js}')

path = root / 'static' / 'app.html'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(html_main, encoding='utf-8')
print(f"Generated app.html with {html_main.count('\n')+1} lines")
