FROM ghcr.io/cirruslabs/flutter:stable AS flutter

WORKDIR /app/apps/user_app
COPY apps/user_app/pubspec.yaml ./
RUN flutter pub get
COPY apps/user_app .
ARG GOOGLE_USER_CLIENT_ID
ARG GOOGLE_ADMIN_CLIENT_ID
ARG JANUS_GIT_SHA=local
# The checked-in web/ directory is canonical; never regenerate it with flutter create during image build.
RUN test -n "$GOOGLE_USER_CLIENT_ID" && test -n "$GOOGLE_ADMIN_CLIENT_ID" && \
    grep -Fq 'Janus · OmniForge' web/index.html && \
    flutter build web --release --base-href /app/ \
      --dart-define=GOOGLE_USER_CLIENT_ID="$GOOGLE_USER_CLIENT_ID" \
      --dart-define=GOOGLE_ADMIN_CLIENT_ID="$GOOGLE_ADMIN_CLIENT_ID"
RUN set -eux; \
    build_id="${JANUS_GIT_SHA:-local}"; \
    main_hash="$(sha256sum build/web/main.dart.js | cut -c1-16)"; \
    grep -Fq 'Janus · OmniForge' build/web/index.html; \
    cp build/web/main.dart.js "build/web/main.${main_hash}.dart.js"; \
    sed -i "s/main.dart.js/main.${main_hash}.dart.js/g" build/web/flutter_bootstrap.js; \
    cp build/web/flutter_bootstrap.js "build/web/flutter_bootstrap.${build_id}.js"; \
    sed -i "s#flutter_bootstrap.js#flutter_bootstrap.${build_id}.js#g" build/web/index.html; \
    printf '%s\n' "$build_id" > build/web/build-id.txt; \
    test -s build/web/build-id.txt; \
    grep -Fq "flutter_bootstrap.${build_id}.js" build/web/index.html

FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY . .
COPY --from=flutter /app/apps/user_app/build/web /app/apps/user_app/build/web
RUN pip install --no-cache-dir --require-hashes -r services/api/requirements.lock

ENV PYTHONPATH=/app:/app/jobs/ingestion-core PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
