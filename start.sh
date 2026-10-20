#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
python manage.py makemigrations shop --noinput
python manage.py migrate --noinput
python manage.py seed_shop
echo
echo "===== Сайт: http://127.0.0.1:8000     Админка: http://127.0.0.1:8000/admin/ ====="
echo
python manage.py runserver
