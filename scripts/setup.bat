@echo off
chcp 65001 >nul
setlocal
REM =====================================================================
REM  Первая установка сайта на Windows. Запуск: двойной клик или
REM     scripts\setup.bat
REM  Нужен Python 3.12+ (python.org, галочка "Add python.exe to PATH").
REM =====================================================================
cd /d "%~dp0.."

echo.
echo === 1/6 Проверка Python ===
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ОШИБКА] Python не найден. Установите Python 3.12+ с https://www.python.org/downloads/
        echo          и при установке отметьте "Add python.exe to PATH".
        pause
        exit /b 1
    )
    set "PY=python"
)
%PY% --version

echo.
echo === 2/6 Виртуальное окружение .venv ===
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo .venv уже есть - пропускаю
)
set "VPY=.venv\Scripts\python.exe"

echo.
echo === 3/6 Установка зависимостей ===
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo === 4/6 Файл настроек .env ===
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Создан .env из .env.example
    "%VPY%" -c "import pathlib,secrets;p=pathlib.Path('.env');t=p.read_text(encoding='utf-8');p.write_text(t.replace('SECRET_KEY=change-me-to-a-long-random-string','SECRET_KEY='+secrets.token_urlsafe(50),1),encoding='utf-8')"
    echo В .env записан новый случайный SECRET_KEY
) else (
    echo .env уже есть - не трогаю
)

echo.
echo === 5/6 База данных и демо-данные ===
"%VPY%" manage.py migrate
if errorlevel 1 goto :error
"%VPY%" manage.py seed_demo
if errorlevel 1 echo [ВНИМАНИЕ] seed_demo не выполнился - сайт будет пустым, но рабочим.

echo.
echo === 6/6 Пользователь для панели управления /admin/ ===
echo Придумайте логин, e-mail (можно пропустить Enter) и пароль.
"%VPY%" manage.py createsuperuser

echo.
echo ============================================================
echo  Готово! Запуск сайта: scripts\run.bat
echo  Сайт:   http://127.0.0.1:8000/
echo  Панель: http://127.0.0.1:8000/admin/
echo ============================================================
pause
exit /b 0

:error
echo.
echo [ОШИБКА] Установка прервана. Прочитайте сообщение выше.
pause
exit /b 1
