# Rolevo all-in-one image: web build + API + worker + scheduler (AZ-002).
# Locked, non-root, immutable-digest friendly. Run migrations separately
# with the migrator role image entrypoint, never at container start.

# ---- web build ----
FROM node:22-slim AS web
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN corepack enable && corepack pnpm install --frozen-lockfile --filter @job-tracking/web
COPY apps/web apps/web
RUN corepack pnpm --filter @job-tracking/web build

# ---- runtime ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    WEB_DIST_DIR=/srv/web
RUN pip install --no-cache-dir --timeout 120 --retries 5 uv==0.9.* supervisor==4.3.*
WORKDIR /srv/api
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
COPY infra/docker/supervisord.conf /etc/supervisord.conf
COPY --from=web /src/apps/web/dist /srv/web
RUN useradd --system --uid 10001 rolevo && chown -R rolevo /srv
USER rolevo
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health/live',timeout=3)"
ENTRYPOINT ["supervisord", "-n", "-c", "/etc/supervisord.conf"]
