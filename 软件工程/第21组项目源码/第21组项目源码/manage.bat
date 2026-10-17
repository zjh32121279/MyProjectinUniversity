@echo off
chcp 65001 >nul 2>nul
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "USER=%ROOT%frontend\user"
set "ADMIN=%ROOT%frontend\bookflow-admin"
set "SUPERADMIN=%ROOT%frontend\bookflow_superadmin"

if /i "%~1"=="start" goto :start
if /i "%~1"=="stop"  goto :stop
if /i "%~1"==""      goto :start

echo Usage: manage.bat [start^|stop]
echo   start - Start all BookFlow services (default)
echo   stop  - Stop all BookFlow services
exit /b 1

:start
echo ========================================
echo   Starting BookFlow Services...
echo ========================================

echo [1/4] Starting Core (backend) on port 8000...
start "BookFlow-Core" cmd /c "cd /d "%BACKEND%" && python -m uvicorn bookflow_core.main:create_app --factory --host 127.0.0.1 --port 8000 --reload"

echo [2/4] Starting User (user) on port 5173...
start "BookFlow-User" cmd /c "cd /d "%USER%" && npx vite --host"

echo [3/4] Starting Admin (admin) on port 5174...
start "BookFlow-Admin" cmd /c "cd /d "%ADMIN%" && npx vite --host"

echo [4/4] Starting Super Admin (super admin) on port 5175...
start "BookFlow-SuperAdmin" cmd /c "cd /d "%SUPERADMIN%" && npx vite --host"

echo(
echo ========================================
echo   All services started!
echo(
echo   ------ Service URLs ------
echo   Core:         http://127.0.0.1:8000
echo   User:         http://localhost:5173
echo   Admin:        http://localhost:5174
echo   Super Admin:  http://localhost:5175
echo(
echo   ------ Login Credentials ------
echo   [Super Admin] http://localhost:5175
echo     Account:  A01-001
echo     Password: BookFlow@123456
echo(
echo   [Admin]      http://localhost:5174
echo     Account:  A02-001
echo     Password: BookFlow@123456
echo(
echo   [User]       http://localhost:5173
echo     Use your registered email/phone
echo     to login (e.g. 13562822936)
echo(
echo   Run "manage.bat stop" to stop all.
echo ========================================
exit /b 0

:stop
echo ========================================
echo   Stopping BookFlow Services...
echo ========================================

rem Kill by port using netstat + taskkill
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 :5173 :5174 :5175" ^| findstr "LISTENING"') do (
    echo Stopping PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)

rem Also try PowerShell fallback in case above missed anything
powershell -NoProfile -Command "8000,5173,5174,5175 | ForEach-Object{ $p=$_; Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }" 2>nul

echo(
echo ========================================
echo   All services stopped.
echo ========================================
exit /b 0
