FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
RUN useradd --create-home --uid 10001 cardiolens
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ARG ALLOW_SYNTHETIC=0
RUN if [ "$ALLOW_SYNTHETIC" = "1" ]; then python -m app.training --synthetic --skip-paper; \
    else CARDIOLENS_REQUIRE_REAL=1 python -m app.training --skip-paper; fi
RUN mkdir -p uploads data/raw && chown -R cardiolens:cardiolens /app
USER cardiolens
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
