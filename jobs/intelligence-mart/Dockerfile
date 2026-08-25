FROM python:3.12.8-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

COPY requirements.lock ./
RUN if [ -s requirements.lock ] && ! grep -q '^# No Python dependencies' requirements.lock; then \
      pip install --no-cache-dir --require-hashes -r requirements.lock; \
    fi
COPY . .

EXPOSE 8080
# The job HTTP entrypoint will be defined with the first implementation.
CMD ["python", "-m", "intelligence_mart"]
