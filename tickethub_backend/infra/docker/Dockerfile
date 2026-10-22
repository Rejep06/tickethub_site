ARG PYTHON_IMAGE=python:3.13-slim-bookworm
FROM ${PYTHON_IMAGE}
ARG REQUIREMENTS_FILE=requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements* /tmp/
RUN pip install --no-cache-dir -r /tmp/${REQUIREMENTS_FILE} \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app
COPY --chown=10001:10001 backend/ /app/
COPY infra/docker/entrypoint.sh /usr/local/bin/tickethub-entrypoint
RUN chmod 755 /usr/local/bin/tickethub-entrypoint \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R 10001:10001 /app/staticfiles /app/media
USER app
EXPOSE 8000
ENTRYPOINT ["tickethub-entrypoint"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--access-logformat", "%(m)s %(U)s %(s)s %(L)s", "--error-logfile", "-"]
