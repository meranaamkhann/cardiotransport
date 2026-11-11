# Deployment and operations

## Configuration

| Variable | Purpose |
| --- | --- |
| CARDIOLENS_ENV | `production` enforces SECRET_KEY and disables seeding |
| DATABASE_URL | SQLAlchemy URL, for example postgresql+psycopg://user:pass@host/db |
| SECRET_KEY | JWT signing key and default source of the encryption key |
| FERNET_KEY | Optional separate key for encrypted notes and review summaries |
| ACCESS_TOKEN_MINUTES | Token lifetime, default 60 |
| TRUST_PROXY | `1` behind nginx so client IPs come from X-Forwarded-For |
| CORS_ORIGINS | Comma-separated origins, empty when the frontend is served from the same host |
| RATE_LIMIT_ENABLED, MAX_UPLOAD_MB, LOG_LEVEL | Rate limiting, upload size, log level |

Generate keys with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Losing FERNET_KEY (or SECRET_KEY when FERNET_KEY is unset) makes stored notes unreadable, so back it up separately from the database.

## Independent deployment

The API image serves the compiled frontend when `frontend/dist` exists; otherwise it serves only `/api`. The frontend image is a static nginx site that proxies `/api` to the `api` service. To host the frontend elsewhere, build it and set `CORS_ORIGINS` on the API.

## Health and logs

`/api/health` is liveness. `/api/health/ready` checks the database and the model. Logs are JSON, one line per request with method, path, status and duration. Passwords, tokens and clinical content are never logged. The audit table records sign-ins, record views, reviews, exports, report generation and consent changes.

## Migrations

`alembic upgrade head` runs on container start. Create a new revision with `alembic revision --autogenerate -m "message"` and review it before committing.

## Backups

- Database: `pg_dump -Fc cardiolens > cardiolens-$(date +%F).dump` nightly, stored off the host, restore with `pg_restore`. Test a restore monthly.
- Uploads volume (research datasets) and the model artifacts directory.
- Keys: SECRET_KEY and FERNET_KEY in a secrets manager.
- Retention: remove research datasets and experiments when a study ends. Patients can leave a clinic at any time, which immediately ends clinician access.

## Hardening checklist before real use

Terminate TLS in front of nginx, rotate keys, move rate limiting to Redis, move tokens to httpOnly cookies with CSRF protection, add email verification and password reset, run a security review, and complete the clinical-safety and regulatory work that a real patient-facing deployment requires.
