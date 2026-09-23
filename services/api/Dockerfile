FROM ghcr.io/cirruslabs/flutter:stable AS flutter

WORKDIR /app/apps/user_app
COPY apps/user_app/pubspec.yaml ./
RUN flutter pub get
COPY apps/user_app .
ARG GOOGLE_USER_CLIENT_ID
ARG GOOGLE_ADMIN_CLIENT_ID
RUN test -n "$GOOGLE_USER_CLIENT_ID" && test -n "$GOOGLE_ADMIN_CLIENT_ID" && \
    flutter create . --platforms web --no-pub && \
    flutter build web --release --base-href /app/ \
      --dart-define=GOOGLE_USER_CLIENT_ID="$GOOGLE_USER_CLIENT_ID" \
      --dart-define=GOOGLE_ADMIN_CLIENT_ID="$GOOGLE_ADMIN_CLIENT_ID"

FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY . .
COPY --from=flutter /app/apps/user_app/build/web /app/apps/user_app/build/web
RUN pip install --no-cache-dir --require-hashes -r services/api/requirements.lock

ENV PYTHONPATH=/app:/app/jobs/ingestion-core PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
