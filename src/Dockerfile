FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=WARNING \
    APP_LOG_EACH_REQUEST=0

# Build-only deps: gcc for NumPy C extensions, then cleanup in same layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Copy resource files and preprocessing script first (changes less than app code)
COPY resources/ resources/
COPY src/preprocess.py /app/

# Run preprocessing during build — bakes a compact model into the image.
# Remove preprocess.py and the .gz afterward to keep image lean.
RUN python preprocess.py \
    && rm -f preprocess.py resources/references.json.gz

# Copy application code last (changes most often — maximizes Docker cache hits)
COPY src/app.py /app/

EXPOSE 8000

# Keep runtime logging minimal for benchmark throughput. Extra workers/threads
# help absorb arrival spikes and reduce queue-driven timeouts.
CMD ["granian", "--interface", "wsgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--blocking-threads", "1", "--backpressure", "512", "--backlog", "2048", "--log-level", "warning", "app:app"]
