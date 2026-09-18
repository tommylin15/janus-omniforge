FROM ghcr.io/cirruslabs/flutter:stable AS flutter-build
WORKDIR /src
COPY apps/user_app apps/user_app
RUN cd apps/user_app && flutter pub get && \
    flutter create . --platforms web --no-pub && \
    flutter build web --release --base-href=/app/ \
        --dart-define=JANUS_API_BASE_URL=https://janus-api-2oo7qbkd5q-uc.a.run.app \
        --dart-define=GOOGLE_USER_CLIENT_ID=131494961796-q066ts6ufuoch6t5uqod0nkqdb5nttjh.apps.googleusercontent.com

FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY . .
COPY --from=flutter-build /src/apps/user_app/build/web apps/user_app/build/web
RUN pip install --no-cache-dir --require-hashes -r services/api/requirements.lock

ENV PYTHONPATH=/app:/app/jobs/ingestion-core PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
