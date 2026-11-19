FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --only-upgrade --no-install-recommends -y zlib1g \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN groupadd --system petcare && useradd --system --gid petcare --home-dir /app petcare

COPY requirements.txt requirements.lock ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt -c requirements.lock

COPY --chown=petcare:petcare . .
RUN mkdir -p /app/instance/pet-images /app/instance/product-images \
    && chown -R petcare:petcare /app/instance

USER petcare
EXPOSE 8000
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "30", "--access-logfile", "-", "--access-logformat", "%(t)s %(m)s %(U)s %(s)s %(L)s", "--error-logfile", "-", "--bind", "0.0.0.0:8000", "wsgi:app"]
