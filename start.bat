@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0" || exit /b 1
title MuzFlowers - сайт

echo.
echo  ==================================================
echo   MuzFlowers: запускаю сайт
echo   (при первом запуске скачаются зависимости)
echo  ==================================================
echo.

rem Временные файлы держим в папке проекта, а не на диске C
if not exist ".tmp" (
  mkdir ".tmp"
  if errorlevel 1 goto err
)
set "TEMP=%~dp0.tmp"
set "TMP=%~dp0.tmp"
set "PIP_CACHE_DIR=%~dp0.tmp\pip"
set "PYTHONUTF8=1"

set "VPY=%~dp0.venv\Scripts\python.exe"
if exist "%VPY%" goto dependencies

rem Ищем Python 3.12 или новее только для создания окружения.
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && set "PY=python"
)
if not defined PY goto no_python

echo [1/4] Создаю окружение Python...
%PY% -m venv .venv
if errorlevel 1 goto err

:dependencies
"%VPY%" -c "import sys; sys.exit(sys.version_info < (3, 12))"
if errorlevel 1 goto bad_venv
echo [2/4] Проверяю нужные программы (нужен интернет, если что-то не установлено)...
"%VPY%" -m pip install -q --disable-pip-version-check --no-input -r requirements.txt -r bot/requirements.txt
if errorlevel 1 goto err

rem Создаём настройки только при первом запуске.
if not exist ".env" (
  copy ".env.example" ".env" >nul
  if errorlevel 1 goto err
)

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
if errorlevel 1 goto err
exit /b 0

:no_python
echo.
echo  Не найден Python 3.12 или новее. Установите его с https://www.python.org/downloads/
echo  (на первом экране установщика поставьте галочку "Add Python to PATH")
echo  и запустите start.bat ещё раз.
echo.
goto err_exit

:bad_venv
echo  Окружение .venv не запускается или использует старый Python.
echo  Переименуйте только папку .venv и запустите start.bat с Python 3.12 или новее.
goto err_exit

:err
echo.
echo  Запуск прервался. Причина указана выше.
echo.
:err_exit
if not "%NO_BROWSER%"=="1" pause
exit /b 1
