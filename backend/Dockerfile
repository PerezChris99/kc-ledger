FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements-prod.lock /tmp/requirements-prod.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements-prod.lock
COPY VERSION /app/VERSION
COPY backend/ ./backend/
ARG LEDGER_GIT_SHA=unknown
ARG LEDGER_RELEASE_CHANNEL=stable
ENV LEDGER_BUILD_SHA=$LEDGER_GIT_SHA LEDGER_RELEASE_CHANNEL=$LEDGER_RELEASE_CHANNEL
RUN python -c 'import os,json,datetime,pathlib;v=pathlib.Path("/app/VERSION").read_text().strip();info={"version":v,"git_sha":os.environ["LEDGER_BUILD_SHA"][:12],"build_time":datetime.datetime.now(datetime.timezone.utc).isoformat(),"channel":os.environ["LEDGER_RELEASE_CHANNEL"],"min_supported_version":"0.0.0"};pathlib.Path("/app/backend/config/build_info.json").write_text(json.dumps(info))'
WORKDIR /app/backend
RUN mkdir -p /app/data && DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" DJANGO_DEBUG=1 python manage.py collectstatic --noinput \
    && groupadd --system --gid 10001 ledger \
    && useradd --system --uid 10001 --gid ledger --home-dir /home/ledger --create-home ledger \
    && chown -R ledger:ledger /app /home/ledger
USER ledger
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py check_db_transition && python manage.py ensure_owner && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 60"]
