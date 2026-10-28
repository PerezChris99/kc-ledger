# Local setup

Copy .env.example to .env and set a strong unique DJANGO_SECRET_KEY and LEDGER_PASSWORD. Run docker compose up --build. The web console is exposed on port 8080 and nginx reverse-proxies API and admin requests to Django.

For local backend development, create a Python 3.11+ virtual environment, install the backend dependencies and run python backend/manage.py migrate followed by python backend/manage.py runserver. For frontend development, run npm install and npm run dev; Vite proxies /api to port 8000.

Never commit .env, the SQLite database, real client records or production credentials. Production requires HTTPS, private network access, strong secrets, regular backups and a tested restore procedure.

## Changelog
- 2026-10-28: Documented initial bootstrap workflow and schema initialization.
