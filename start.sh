#!/usr/bin/env bash
# Запуск сайта MuzFlowers на Mac / Linux:  ./start.sh
set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || { echo "Не найден Python 3. Установите его: https://www.python.org/downloads/"; exit 1; }

[ -d .venv ] || { echo "[1/4] Готовлю рабочую папку для программ..."; "$PY" -m venv .venv; }
echo "[2/4] Проверяю нужные программы..."
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
[ -f .env ] || cp .env.example .env

echo "[3/4] Готовлю базу данных..."
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_shop

echo
echo "==================================================="
echo " Готово!  Сайт:             http://127.0.0.1:8000"
echo "          Панель владельца: http://127.0.0.1:8000/admin/"
echo " При первом входе в панель придумайте логин и пароль."
echo " Остановить сайт: Ctrl + C"
echo "==================================================="
echo
exec .venv/bin/python manage.py runserver 127.0.0.1:8000
