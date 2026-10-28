@echo off
chcp 65001 >nul
REM Статическая демо-копия сайта в папку dist (открыть dist\index.html в браузере)
cd /d "%~dp0.."
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" scripts\export_static.py --out dist %*
pause
