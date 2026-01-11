#!/bin/bash
# ===========================================
# 7TY.VN - HƯỚNG DẪN DEPLOY LÊN CÁC NỀN TẢNG MIỄN PHÍ
# ===========================================

echo "================================================"
echo "  7TY.VN DEPLOYMENT GUIDE"
echo "================================================"

# ============================================
# OPTION 1: RAILWAY (Đề xuất - Dễ nhất)
# ============================================
deploy_railway() {
    echo ""
    echo "🚂 RAILWAY DEPLOYMENT"
    echo "====================="
    echo "1. Truy cập: https://railway.app"
    echo "2. Đăng nhập bằng GitHub"
    echo "3. New Project -> Deploy from GitHub repo"
    echo "4. Chọn repo: 7ty_system"
    echo "5. Thêm PostgreSQL:"
    echo "   - New -> Database -> PostgreSQL"
    echo "6. Cấu hình Environment Variables:"
    echo "   DATABASE_TYPE=postgres"
    echo "   DB_HOST=\${{Postgres.PGHOST}}"
    echo "   DB_PORT=\${{Postgres.PGPORT}}"
    echo "   DB_USER=\${{Postgres.PGUSER}}"
    echo "   DB_PASSWORD=\${{Postgres.PGPASSWORD}}"
    echo "   DB_NAME=\${{Postgres.PGDATABASE}}"
    echo "   SECRET_KEY=<generate-strong-key>"
    echo "7. Deploy!"
    echo ""
    echo "🔗 URL: https://your-app.railway.app"
}

# ============================================
# OPTION 2: RENDER
# ============================================
deploy_render() {
    echo ""
    echo "🎨 RENDER DEPLOYMENT"
    echo "===================="
    echo "1. Truy cập: https://render.com"
    echo "2. Đăng nhập bằng GitHub"
    echo "3. New -> Blueprint"
    echo "4. Chọn repo có file render.yaml"
    echo "5. Deploy Blueprint"
    echo ""
    echo "Hoặc deploy thủ công:"
    echo "1. New -> Web Service"
    echo "2. Connect GitHub repo"
    echo "3. Settings:"
    echo "   - Environment: Python 3"
    echo "   - Build Command: pip install -r requirements.txt"
    echo "   - Start Command: uvicorn main:app --host 0.0.0.0 --port \$PORT"
    echo "4. New -> PostgreSQL (Free tier)"
    echo "5. Link database to web service"
    echo ""
    echo "🔗 URL: https://your-app.onrender.com"
}

# ============================================
# OPTION 3: FLY.IO
# ============================================
deploy_flyio() {
    echo ""
    echo "🪰 FLY.IO DEPLOYMENT"
    echo "===================="
    echo "1. Cài đặt flyctl:"
    echo "   curl -L https://fly.io/install.sh | sh"
    echo ""
    echo "2. Đăng nhập:"
    echo "   fly auth login"
    echo ""
    echo "3. Launch app:"
    echo "   fly launch"
    echo ""
    echo "4. Tạo PostgreSQL:"
    echo "   fly postgres create --name 7ty-db"
    echo "   fly postgres attach 7ty-db"
    echo ""
    echo "5. Set secrets:"
    echo "   fly secrets set SECRET_KEY=your-secret-key"
    echo "   fly secrets set DATABASE_TYPE=postgres"
    echo ""
    echo "6. Deploy:"
    echo "   fly deploy"
    echo ""
    echo "🔗 URL: https://7ty.fly.dev"
}

# ============================================
# OPTION 4: KOYEB
# ============================================
deploy_koyeb() {
    echo ""
    echo "🥝 KOYEB DEPLOYMENT"
    echo "==================="
    echo "1. Truy cập: https://www.koyeb.com"
    echo "2. Đăng nhập bằng GitHub"
    echo "3. Create App -> GitHub"
    echo "4. Chọn repo và branch"
    echo "5. Settings:"
    echo "   - Builder: Dockerfile"
    echo "   - Port: 8000"
    echo "   - Instance: Nano (free)"
    echo "6. Environment Variables:"
    echo "   DATABASE_TYPE=sqlite"
    echo "   SECRET_KEY=your-secret-key"
    echo "7. Deploy!"
    echo ""
    echo "🔗 URL: https://your-app.koyeb.app"
}

# ============================================
# OPTION 5: HUGGING FACE SPACES (Miễn phí vĩnh viễn)
# ============================================
deploy_huggingface() {
    echo ""
    echo "🤗 HUGGING FACE SPACES"
    echo "======================"
    echo "1. Truy cập: https://huggingface.co/spaces"
    echo "2. Create new Space"
    echo "3. Chọn Docker SDK"
    echo "4. Push code:"
    echo "   git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/7ty"
    echo "   git push hf main"
    echo ""
    echo "Lưu ý: Chỉ hỗ trợ SQLite (không persistent)"
    echo ""
    echo "🔗 URL: https://YOUR_USERNAME-7ty.hf.space"
}

echo ""
echo "Chọn nền tảng để xem hướng dẫn:"
echo "1. Railway (Đề xuất)"
echo "2. Render"
echo "3. Fly.io"
echo "4. Koyeb"
echo "5. Hugging Face Spaces"
echo ""
