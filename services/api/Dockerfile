FROM python:3.12.8-slim-bookworm AS api-python-base

WORKDIR /app
# Shared Python runtime for the public API and owner-private pipeline.
COPY services/api/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .

ENV PYTHONPATH=/app:/app/jobs/ingestion-core PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080

# Keep the private pipeline independent from the Flutter build/output. Because
# this target precedes the Flutter stage, `docker build --target=private-pipeline`
# does not pull or execute the Flutter builder.
FROM api-python-base AS private-pipeline
CMD ["python", "-m", "services.api.private_pipeline_runtime"]

FROM ghcr.io/cirruslabs/flutter:stable AS flutter

WORKDIR /app/apps/user_app
COPY apps/user_app/pubspec.yaml ./
RUN flutter pub get
COPY apps/user_app .
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pil && rm -rf /var/lib/apt/lists/*
RUN python3 tool/generate_brand_assets.py
ARG GOOGLE_USER_CLIENT_ID
ARG GOOGLE_ADMIN_CLIENT_ID
ARG JANUS_GIT_SHA=local
# The checked-in web/ directory is canonical; never regenerate it with flutter create during image build.
RUN test -n "$GOOGLE_USER_CLIENT_ID" && test -n "$GOOGLE_ADMIN_CLIENT_ID" && \
    grep -Fq 'Janus · OmniForge' web/index.html && \
    flutter build web --release -t lib/final_visual.dart --base-href /app/ \
      --dart-define=GOOGLE_USER_CLIENT_ID="$GOOGLE_USER_CLIENT_ID" \
      --dart-define=GOOGLE_ADMIN_CLIENT_ID="$GOOGLE_ADMIN_CLIENT_ID"
RUN set -eux; \
    build_id="${JANUS_GIT_SHA:-local}"; \
    main_hash="$(sha256sum build/web/main.dart.js | cut -c1-16)"; \
    grep -Fq 'Janus · OmniForge' build/web/index.html; \
    test -s build/web/icons/Icon-192.png; \
    test -s build/web/icons/Icon-512.png; \
    test -s build/web/icons/maskable-512.png; \
    test -s build/web/assets/assets/branding/janus_app_icon_512.png; \
    cp build/web/main.dart.js "build/web/main.${main_hash}.dart.js"; \
    sed -i "s/main.dart.js/main.${main_hash}.dart.js/g" build/web/flutter_bootstrap.js; \
    cp build/web/flutter_bootstrap.js "build/web/flutter_bootstrap.${build_id}.js"; \
    sed -i "s#flutter_bootstrap.js#flutter_bootstrap.${build_id}.js#g" build/web/index.html; \
    printf '%s\n' "$build_id" > build/web/build-id.txt; \
    test -s build/web/build-id.txt; \
    grep -Fq "flutter_bootstrap.${build_id}.js" build/web/index.html

FROM api-python-base AS api
# Legacy static Admin code is excluded by .dockerignore; Flutter /app/admin is the active frontend.
COPY --from=flutter /app/apps/user_app/build/web /app/apps/user_app/build/web

EXPOSE 8080
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
