# Сайт MuzFlowers. Локально проще использовать start.bat; Docker нужен для сервера.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0 \
    DJANGO_DATA_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY --chown=app:app . .
# Ключ нужен только для сборки статики и не сохраняется в настройках запуска.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && mkdir -p /data \
    && chown -R app:app /data /app/staticfiles

# База SQLite и фотографии живут здесь при запуске без PostgreSQL.
VOLUME /data
EXPOSE 8000
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python docker_healthcheck.py

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_shop && gunicorn muzflowers.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
