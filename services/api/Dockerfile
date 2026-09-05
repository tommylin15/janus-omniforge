FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir --require-hashes -r services/api/requirements.lock

ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
