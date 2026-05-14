# AGENTS.md - Rinha de Backend 2026 - Python Implementation

## Overview

This repository implements a fraud detection API for the "Rinha de Backend 2026" challenge. The system receives transaction data, vectorizes it, finds the 5 most similar historical transactions using KNN, and decides whether to approve or deny the transaction based on the fraud rate among those neighbors.

The implementation is optimized for performance and resource constraints, using NumPy for vector operations and memory-mapped files for efficient data access.

## Project Structure

```
.
├── AGENTS.md                 # This file
├── docs/notes.md             # Detailed challenge specification
├── requirements.txt          # Python dependencies
├── resources/                # Dataset and normalization files (generated)
├── src/
│   ├── Dockerfile            # Container build definition
│   ├── app.py                # Main API application (Falcon framework)
│   └── preprocess.py         # Dataset preprocessing script
```

## Key Components

### 1. API (`src/app.py`)

- **Framework**: Falcon (minimalist Python web framework)
- **Server**: Gunicorn (WSGI server)
- **Endpoints**:
  - `GET /ready` - Health check endpoint
  - `POST /fraud-score` - Main fraud detection endpoint

### 2. Preprocessing (`src/preprocess.py`)

- Downloads the reference dataset from the official challenge repository
- Decompresses and converts the JSON data into binary NumPy arrays
- Generates `vectors.bin` and `labels.bin` for efficient runtime access

### 3. Resources

- `normalization.json` - Constants for feature scaling
- `mcc_risk.json` - Merchant Category Code risk mapping
- `vectors.bin` - Binary file containing 3M reference vectors (14D each)
- `labels.bin` - Binary file containing fraud labels for reference vectors

## Architecture & Performance Optimizations

### Vector Search

- **Method**: Exact KNN using brute-force Euclidean distance
- **Implementation**: NumPy's `einsum` for efficient distance calculation
- **Optimization**: `argpartition` for O(N) selection of top 5 neighbors instead of full sort

### Memory Management

- **Memory Mapping**: Reference datasets are loaded using `np.memmap` to share memory between API instances
- **Single Worker**: Gunicorn configured with 1 worker to avoid CPU contention in constrained environment

### Error Handling

- **Graceful Degradation**: Any internal error returns `{"approved": true, "fraud_score": 0.0}` with HTTP 200 to avoid -5 point penalty

## Essential Commands

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Download and preprocess dataset
python src/preprocess.py
```

### Running the API Locally

```bash
# Start the API server
gunicorn -b 0.0.0.0:9999 -w 1 src.app:app --worker-class sync
```

### Building and Running with Docker

```bash
# Build the image
docker build -t fraud-detection-api src/

# Run the container
docker run -p 9999:8000 fraud-detection-api
```

## Deployment Constraints

- **Port**: API must listen on port 8000 inside container (exposed as 9999 via load balancer)
- **Resources**: Maximum 1 CPU and 350MB memory for entire docker-compose stack
- **Network**: Bridge mode only (no host networking)
- **Load Balancer**: Must distribute requests round-robin, no business logic allowed

## Key Implementation Details

### Vectorization Process

The transaction payload is converted to a 14-dimensional vector following the exact specification in `docs/notes.md`. Each dimension is normalized to [0, 1] using precomputed constants, with -1 used as a sentinel value for missing data.

### KNN Algorithm

1. Calculate squared Euclidean distances between query vector and all reference vectors using NumPy's `einsum`
2. Use `argpartition` to efficiently find indices of 5 nearest neighbors
3. Calculate fraud score as the fraction of fraudulent neighbors
4. Approve transaction if `fraud_score < 0.6`

### Performance Considerations

- All preprocessing happens at build time (in Dockerfile)
- No disk I/O during request processing
- Minimal Python overhead in request path
- Leverages NumPy's optimized C implementations for vector operations

## Testing

The official test uses K6 to send transaction payloads and measure performance. The test script is not included in this repository but is available in the official challenge repository.

Key metrics:
- p99 latency (target < 2000ms)
- Error rate (must be < 15%)
- Detection accuracy (TP, TN, FP, FN)

## Gotchas & Important Notes

1. **Memory Mapping**: The use of `np.memmap` is critical for sharing reference data between multiple API instances without exceeding memory limits
2. **Error Responses**: Never return HTTP 500 - always return a 200 with a safe default response
3. **Resource Limits**: Every optimization counts - profile and measure impact of changes
4. **Build Time vs Runtime**: All heavy computation must happen during Docker build, not at runtime
5. **Vector Order**: The 14 dimensions must be in the exact order specified in the documentation