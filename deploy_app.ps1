# Script deploy app.html - Chi can luu file va refresh browser!
# Container 7ty_app su dung BIND MOUNT nen file local = file trong container
# Su dung: .\deploy_app.ps1

$localFile = "C:\Users\LaptopHL\DU_AN\7ty_system\static\app.html"
$backupFile = "C:\Users\LaptopHL\DU_AN\7ty_system\static\app.html.backup_latest"

Write-Host "========================================"
Write-Host "  Check & Backup app.html              "
Write-Host "========================================"

# Step 1: Kiem tra file local ton tai
Write-Host "`n[1/3] Kiem tra file local..."
if (-not (Test-Path $localFile)) {
    Write-Host "ERROR: File khong ton tai: $localFile" -ForegroundColor Red
    exit 1
}
$localSize = (Get-Item $localFile).Length
Write-Host "  OK - File size: $localSize bytes" -ForegroundColor Green

# Step 2: Kiem tra encoding
Write-Host "`n[2/3] Kiem tra encoding..."
$content = Get-Content $localFile -First 10 -Raw
if ($content -match "UTF-8") {
    Write-Host "  OK - UTF-8 charset found" -ForegroundColor Green
} else {
    Write-Host "  WARNING - Check encoding" -ForegroundColor Yellow
}

# Step 3: Tao backup
Write-Host "`n[3/3] Tao backup..."
Copy-Item $localFile $backupFile -Force
Write-Host "  OK - Backup: $backupFile" -ForegroundColor Green

Write-Host "`n========================================"
Write-Host "  KHONG CAN COPY LEN DOCKER!           " -ForegroundColor Cyan
Write-Host "  Container dang bind mount folder:    "
Write-Host "  C:\...\static -> /app/static         "
Write-Host "========================================"
Write-Host "`nFile da san sang! Chi can:"
Write-Host "  1. Luu file trong VS Code (Ctrl+S)"
Write-Host "  2. Refresh browser (Ctrl+F5)"
Write-Host ""
