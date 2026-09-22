FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY . .
# Pre-split Web artifact from 5d24d063. Keep the
# legacy Chat UI while Janus source and omniAgent deployment are separate.
RUN echo 'b2cd74213703d606dec511fa2c43befbc5518a8685f5c2bf3c19eab7c7e72825  services/api/legacy-user-app-web.tar.gz' | sha256sum -c - && \
    rm -rf apps/user_app/build/web && mkdir -p apps/user_app/build/web && \
    tar -xzf services/api/legacy-user-app-web.tar.gz -C apps/user_app/build/web && \
    grep -q '<base href="/app/">' apps/user_app/build/web/index.html && \
    grep -q '/api/v1/me/chats/threads' apps/user_app/build/web/main.dart.js && \
    grep -q '131494961796-samjcgtts8kkprjs5nv7kh2qts92su0k.apps.googleusercontent.com' apps/user_app/build/web/main.dart.js
RUN pip install --no-cache-dir --require-hashes -r services/api/requirements.lock

ENV PYTHONPATH=/app:/app/jobs/ingestion-core PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
