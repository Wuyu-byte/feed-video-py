FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN mkdir -p /app/.run/uploads && chown -R app:app /app

USER app

FROM base AS api
EXPOSE 8080
CMD ["python", "-m", "app.main"]

FROM base AS worker
CMD ["python", "-m", "app.worker"]
