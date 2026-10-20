@echo off
chcp 65001 >nul
cd /d %~dp0
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 goto err
call .venv\Scripts\activate
python -m pip install -q -r requirements.txt
if errorlevel 1 goto err
if not exist .env copy .env.example .env >nul
python manage.py makemigrations shop --noinput
python manage.py migrate --noinput
python manage.py seed_shop
echo.
echo ===== Сайт: http://127.0.0.1:8000     Админка: http://127.0.0.1:8000/admin/ =====
echo.
python manage.py runserver
goto :eof
:err
echo.
echo Что-то пошло не так. Установите Python 3.10+ с python.org (галочка "Add Python to PATH") и запустите снова.
pause
