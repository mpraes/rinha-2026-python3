FROM python:3.12-slim-bookworm AS build

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-build.txt /app/
RUN pip install --no-cache-dir -r requirements-build.txt

COPY resources/ resources/
COPY src/preprocess.py /app/

RUN python preprocess.py \
    && rm -f preprocess.py resources/references.json.gz

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=WARNING \
    APP_LOG_EACH_REQUEST=0

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=build /app/resources/ resources/
COPY src/app.py /app/

EXPOSE 8000

CMD ["granian", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--runtime-threads", "4", "--interface", "asgi"]
