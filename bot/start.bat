@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0" || exit /b 1
title MuzFlowers - Telegram-бот

echo.
echo  ==================================================
echo   MuzFlowers: запускаю Telegram-бота
echo   (при первом запуске скачаются зависимости)
echo  ==================================================
echo.

rem Общее окружение сайта и бота находится в корне проекта.
set "ROOT=%~dp0..\"
set "VPY=%~dp0..\.venv\Scripts\python.exe"
set "PYTHONPATH=%~dp0"
set "PYTHONUTF8=1"
if not exist "%ROOT%.tmp" mkdir "%ROOT%.tmp"
if errorlevel 1 goto err
set "TEMP=%ROOT%.tmp"
set "TMP=%ROOT%.tmp"
set "PIP_CACHE_DIR=%ROOT%.tmp\pip"

if exist "%VPY%" goto dependencies

rem Ищем Python 3.12 или новее только для создания общего окружения.
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && set "PY=python"
)
if not defined PY goto no_python

echo [1/3] Создаю общее окружение Python...
%PY% -m venv "%ROOT%.venv"
if errorlevel 1 goto err

:dependencies
"%VPY%" -c "import sys; sys.exit(sys.version_info < (3, 12))"
if errorlevel 1 goto bad_venv
echo [2/3] Проверяю нужные программы (нужен интернет, если что-то не установлено)...
"%VPY%" -m pip install -q --disable-pip-version-check --no-input -r "%ROOT%requirements.txt" -r requirements.txt
if errorlevel 1 goto err

rem У бота свой .env: он не заменяет и не копирует секреты сайта.
if not exist ".env" (
  copy ".env.example" ".env" >nul
  if errorlevel 1 goto err
  echo.
  echo  ==================================================
  echo   Нужно один раз вписать ключ бота.
  echo   Сейчас откроется файл .env - вставьте ключ после BOT_TOKEN=
  echo   Где взять ключ: Telegram - @BotFather - /mybots - ваш бот - API Token.
  echo   Сохраните файл клавишами Ctrl+S, закройте Блокнот и запустите start.bat ещё раз.
  echo  ==================================================
  echo.
  start "" notepad ".env"
  pause
  exit /b 0
)

echo [3/3] Запускаю бота. Окно не закрывайте, пока бот должен работать.
echo       Сначала запустите start.bat в корне проекта и дождитесь сайта на порту 8000.
echo       Остановить бота: закройте это окно или нажмите Ctrl + C.
echo.
set "WAIT=15"

:run
"%VPY%" -m flowerbot
set "CODE=%errorlevel%"
if "%CODE%"=="0" exit /b 0
if "%CODE%"=="2" goto settings
if "%CODE%"=="3" goto no_connection

rem При сбое увеличиваем паузу, чтобы не перегружать сайт и Telegram повторными запусками.
echo.
echo  Бот остановился из-за ошибки - её текст выше. Запускаю заново через %WAIT% сек.
echo  Остановить: закройте это окно.
set /a PINGS=WAIT+1
ping -n %PINGS% 127.0.0.1 >nul
set /a WAIT=WAIT*2
if %WAIT% gtr 300 set "WAIT=300"
goto run

:no_connection
echo  Нет связи с Telegram или сайтом. Проверьте, что сайт запущен и интернет работает.
echo  Пробую снова через 15 секунд. Остановить: закройте это окно.
ping -n 16 127.0.0.1 >nul
goto run

:settings
echo.
echo  Исправьте то, что написано выше, сохраните настройки и запустите bot\start.bat ещё раз.
echo  Не запускайте вторую копию бота, если первая уже работает.
echo.
pause
exit /b 2

:no_python
echo.
echo  Не найден Python 3.12 или новее. Установите его с https://www.python.org/downloads/
echo  (на первом экране установщика поставьте галочку "Add Python to PATH")
echo  и запустите start.bat ещё раз.
echo.
pause
exit /b 1

:bad_venv
echo  Общее окружение .venv не запускается или использует старый Python.
echo  Закройте сайт и бота, переименуйте только папку .venv в корне проекта
echo  и запустите start.bat с Python 3.12 или новее.
pause
exit /b 1

:err
echo.
echo  Запуск прервался. Причина указана выше. Проверьте интернет и запустите start.bat ещё раз.
echo  Если не помогло - пришлите фото этого окна разработчику.
echo.
pause
exit /b 1
