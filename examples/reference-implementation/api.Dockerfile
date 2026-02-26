FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends openssl curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app/apps/api

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api /app/apps/api

EXPOSE 8000
