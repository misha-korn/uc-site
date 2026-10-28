@echo off
chcp 65001 >nul
setlocal
REM =====================================================================
REM  Запуск сайта на компьютере для разработки (Windows).
REM     scripts\run.bat           - uvicorn с автоперезагрузкой
REM     scripts\run.bat django    - встроенный сервер Django (runserver)
REM  Остановка: Ctrl+C
REM =====================================================================
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo Сначала выполните scripts\setup.bat
    pause
    exit /b 1
)
set "VPY=.venv\Scripts\python.exe"

"%VPY%" manage.py migrate --noinput

echo.
echo  Сайт:   http://127.0.0.1:8000/
echo  Панель: http://127.0.0.1:8000/admin/
echo  Остановить: Ctrl+C
echo.

if /i "%~1"=="django" (
    "%VPY%" manage.py runserver 127.0.0.1:8000
) else (
    "%VPY%" -m uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
)
