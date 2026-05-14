FROM python:3.12-slim-bookworm

WORKDIR /app

# Build-only deps: gcc for NumPy C extensions, then cleanup in same layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir falcon gunicorn numpy requests

# Copy resource files and preprocessing script first (changes less than app code)
COPY resources/ resources/
COPY src/preprocess.py /app/

# Run preprocessing during build — bakes vectors.bin and labels.bin into the image.
# Remove preprocess.py and the .gz afterward to keep image lean.
RUN python preprocess.py \
    && rm -f preprocess.py resources/references.json.gz

# Copy application code last (changes most often — maximizes Docker cache hits)
COPY src/app.py /app/

EXPOSE 8000

# Single sync worker: the KNN search is CPU-bound (vectorized NumPy over 3M rows).
# With a 1 CPU / 350MB limit shared across 2 API instances + load balancer,
# multiple workers would context-switch during einsum and slow every request.
# The sync worker class avoids async overhead — each request runs the full
# normalization + brute-force search synchronously, which is the hot path.
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "1", "app:app", "--worker-class", "sync"]
