FROM python:3.12.8-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/jobs/ingestion-core \
    PORT=8080

COPY requirements.lock ./
RUN if [ -s requirements.lock ] && ! grep -q '^# No Python dependencies' requirements.lock; then \
      pip install --no-cache-dir --require-hashes -r requirements.lock; \
    fi
COPY . .

EXPOSE 8080
CMD ["python", "-m", "ingestion_core"]
