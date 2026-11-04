@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MuzFlowers - сайт

echo.
echo  ==================================================
echo   MuzFlowers: запускаю сайт
echo   (в первый раз это займёт 2-3 минуты - ничего не закрывайте)
echo  ==================================================
echo.

rem Временные файлы держим в папке проекта, а не на диске C
if not exist ".tmp" mkdir ".tmp"
set "TEMP=%~dp0.tmp"
set "TMP=%~dp0.tmp"
set "PIP_CACHE_DIR=%~dp0.tmp\pip"
set "PYTHONUTF8=1"

rem Ищем Python
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY goto no_python

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Готовлю рабочую папку для программ...
  %PY% -m venv .venv
  if errorlevel 1 goto err
)
set "VPY=%~dp0.venv\Scripts\python.exe"

echo [2/4] Проверяю нужные программы (нужен интернет, если что-то не установлено)...
"%VPY%" -m pip install -q --disable-pip-version-check --no-input -r requirements.txt
if errorlevel 1 goto err

rem Файл настроек от прошлой версии сайта (PostgreSQL, Redis, Celery) новому сайту не нужен: откладываем его, ничего не удаляя
if exist ".env" findstr /b /c:"CELERY_" /c:"DB_NAME=" /c:"USE_REDIS=" ".env" >nul && (
  echo Нашёл старый файл настроек - сохраняю его как .env.old и создаю новый.
  move /y ".env" ".env.old" >nul
)
if not exist ".env" copy ".env.example" ".env" >nul

echo [3/4] Готовлю базу данных...
"%VPY%" manage.py migrate --noinput
if errorlevel 1 goto err
"%VPY%" manage.py seed_shop
if errorlevel 1 goto err

echo.
echo  ==================================================
echo   Готово! Сайт:           http://127.0.0.1:8000
echo           Панель владельца: http://127.0.0.1:8000/admin/
echo.
echo   При первом входе в панель придумайте логин и пароль.
echo   Остановить сайт: закройте это окно или нажмите Ctrl + C.
echo  ==================================================
echo.

if not "%NO_BROWSER%"=="1" start "" /b cmd /c "ping -n 5 127.0.0.1 >nul & start "" http://127.0.0.1:8000/"

echo [4/4] Сайт работает. Окно не закрывайте, пока сайтом пользуетесь.
echo.
"%VPY%" manage.py runserver 127.0.0.1:8000
goto :eof

:no_python
echo.
echo  Не найден Python. Установите его с https://www.python.org/downloads/
echo  (на первом экране установщика поставьте галочку "Add Python to PATH")
echo  и запустите start.bat ещё раз.
echo.
pause
goto :eof

:err
echo.
echo  Что-то пошло не так (текст ошибки - выше). Проверьте интернет и запустите start.bat ещё раз.
echo  Если не помогло - пришлите разработчику фото этого окна.
echo.
pause
