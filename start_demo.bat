@echo off
chcp 65001 >nul
title NIDS SOC Demo Launcher
color 0A

:: Luôn chuyển đường dẫn về thư mục chứa file .bat này
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║      AWS NIDS SOC - DEMO LAUNCHER v2.0          ║
echo  ║      Trung tam Dieu hanh An ninh mang           ║
echo  ╚══════════════════════════════════════════════════╝
echo.

echo [1/3] Kiem tra Python environment...
if exist "%~dp0myenv\Scripts\python.exe" (
    set "PYTHON=%~dp0myenv\Scripts\python.exe"
    set "STREAMLIT=%~dp0myenv\Scripts\streamlit.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
    set "STREAMLIT=%~dp0.venv\Scripts\streamlit.exe"
) else (
    set "PYTHON=python"
    set "STREAMLIT=streamlit"
)
echo     [OK] Su dung: %PYTHON%

echo.
echo [2/3] Khoi dong Attack API (cong 5000 cho QR demo)...
start "NIDS Attack API - QR Demo" cmd /k "cd /d "%~dp0" && "%PYTHON%" attack_api.py"

echo     [OK] Attack API dang chay tai http://localhost:5000

timeout /t 2 /nobreak >nul

echo.
echo [3/3] Khoi dong Dashboard (Streamlit)...
echo     [OK] Dashboard dang mo tai http://localhost:8501
echo.
echo ════════════════════════════════════════════════════
echo  HUONG DAN DEMO NHANH:
echo.
echo  KICH BAN 1: Nhan nut [Mang Binh thuong] tren sidebar
echo  KICH BAN 2: Nhan nut [Bao DDoS]
echo  KICH BAN 3: Nhan nut [MULTI-VECTOR] ^<-- WOW FACTOR!
echo  KICH BAN 4: Nhan nut [Port Scan]
echo.
echo  QR CODE DEMO:
echo  1. Mo terminal moi, chay: ngrok http 5000
echo  2. Lay URL ngrok (vd: https://abc.ngrok.io)
echo  3. Tao QR tai: https://qr-code-generator.com/
echo  4. Chieu QR len man hinh - moi thay co quet!
echo ════════════════════════════════════════════════════
echo.

"%STREAMLIT%" run dashboard.py --server.headless false --server.port 8501

pause
