# Khởi động Dashboard + Attack API cùng lúc (PowerShell)
# Chạy: .\start_demo.ps1

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║      AWS NIDS SOC - DEMO LAUNCHER v2.0          ║" -ForegroundColor Cyan
Write-Host "  ║      Trung tâm Điều hành An ninh mạng           ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = Get-Location }
Set-Location $scriptDir

# Xác định Python
$python = if (Test-Path "$scriptDir\.venv\Scripts\python.exe") { "$scriptDir\.venv\Scripts\python.exe" }
          elseif (Test-Path "$scriptDir\myenv\Scripts\python.exe") { "$scriptDir\myenv\Scripts\python.exe" }
          else { "python" }

$streamlit = if (Test-Path "$scriptDir\.venv\Scripts\streamlit.exe") { "$scriptDir\.venv\Scripts\streamlit.exe" }
             elseif (Test-Path "$scriptDir\myenv\Scripts\streamlit.exe") { "$scriptDir\myenv\Scripts\streamlit.exe" }
             else { "streamlit" }

Write-Host "[1/2] Khởi động Attack API (port 5000)..." -ForegroundColor Yellow
Start-Process -FilePath "cmd" -ArgumentList "/k", "cd /d `"$scriptDir`" && `"$python`" attack_api.py" -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "[2/2] Khởi động Dashboard Streamlit (port 8501)..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Dashboard: http://localhost:8501" -ForegroundColor Green
Write-Host "  Attack API: http://localhost:5000" -ForegroundColor Green
Write-Host ""
Write-Host "  QR Demo: chạy 'ngrok http 5000' trong terminal riêng" -ForegroundColor Magenta
Write-Host ""

& $streamlit run dashboard.py --server.headless false --server.port 8501
