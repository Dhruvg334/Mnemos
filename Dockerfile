# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN python -m venv /opt/venv     && /opt/venv/bin/pip install --upgrade pip setuptools wheel     && /opt/venv/bin/pip install .

FROM python:3.12-slim AS runtime

ARG APP_VERSION=0.1.0
ENV PATH="/opt/venv/bin:$PATH"     PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     APP_VERSION="${APP_VERSION}"     PORT=8000

RUN groupadd --system --gid 10001 mnemos     && useradd --system --uid 10001 --gid mnemos --create-home mnemos

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN chmod +x /app/scripts/container-entrypoint.sh     && chown -R mnemos:mnemos /app

USER mnemos
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3     CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/health/live', timeout=3)"

ENTRYPOINT ["/app/scripts/container-entrypoint.sh"]
CMD ["api"]
