FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY . .

# Reuse the hash-locked runtime set used by ingestion.  It includes DuckDB,
# PyIceberg, PyArrow and psycopg required by the read-only Web runtime.
COPY jobs/ingestion-core/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

ENV PYTHONPATH=/app:/app/jobs/ingestion-core \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080
EXPOSE 8080

CMD ["python", "-m", "apps.web.server"]
