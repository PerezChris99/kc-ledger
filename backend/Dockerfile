FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3-dev libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "Django>=5.2,<5.3" "django-ninja>=1.3,<2" "APScheduler>=3.10,<4" "pandas>=2.2,<3" "WeasyPrint>=62,<70" "gunicorn>=22,<24" "whitenoise>=6.7,<7"
COPY backend/ ./backend/
WORKDIR /app/backend
RUN mkdir -p /app/data && python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py ensure_owner && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 60"]
