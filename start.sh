#!/usr/bin/env bash
# Запуск сайта MuzFlowers на macOS / Linux: bash start.sh
set -eu
cd -- "$(dirname -- "$0")"

if [ ! -x .venv/bin/python ]; then
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    printf '%s\n' 'Для запуска нужен Python 3.12 или новее.'
    exit 1
  fi
  printf '%s\n' '[1/4] Создаю окружение Python...'
  python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
  printf '%s\n' 'Окружение .venv не запускается или использует старый Python. Переименуйте только папку .venv и повторите запуск.'
  exit 1
fi
echo "[2/4] Проверяю нужные программы..."
.venv/bin/python -m pip install -q --disable-pip-version-check --no-input -r requirements.txt -r bot/requirements.txt
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
