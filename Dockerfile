# Сайт MuzFlowers для запуска на сервере или хостинге с Docker.
# Сборка:  docker build -t muzflowers .
# Запуск:  docker run -d -p 8000:8000 -v muz-data:/data --env-file .env.production muzflowers
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_DATA_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Собираем статику (стили, скрипты, картинки) заранее; ключ нужен только для сборки
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

# База и фото букетов живут в /data — этот том нужно сохранять
VOLUME /data
EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_shop && gunicorn muzflowers.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
