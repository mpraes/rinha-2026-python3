import gzip
import json
import logging
import numpy as np
import os
import requests
from sklearn.linear_model import SGDClassifier

MODEL_PATH = "resources/model.json"

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("preprocess")

def download_file(url, local_path):
    """Download a file from URL to local path if it doesn't already exist."""
    if os.path.exists(local_path):
        logger.info("download_skip file=%s", os.path.basename(local_path))
        return

    logger.info("download_start file=%s url=%s", os.path.basename(local_path), url)
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.info("download_done file=%s", os.path.basename(local_path))

def download_dataset():
    """Download the main reference dataset."""
    url = "https://github.com/zanfranceschi/rinha-de-backend-2026/raw/main/resources/references.json.gz"
    local_path = "resources/references.json.gz"
    download_file(url, local_path)

def download_auxiliary_files():
    """Download auxiliary JSON files needed for vectorization."""
    files = [
        ("https://github.com/zanfranceschi/rinha-de-backend-2026/raw/main/resources/mcc_risk.json", "resources/mcc_risk.json"),
        ("https://github.com/zanfranceschi/rinha-de-backend-2026/raw/main/resources/normalization.json", "resources/normalization.json")
    ]
    
    for url, local_path in files:
        download_file(url, local_path)


def train_model(vectors, labels):
    """Train a very fast linear classifier for low-latency inference."""
    logger.info("train_model_start samples=%s features=%s", vectors.shape[0], vectors.shape[1])
    model = SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=1e-5,
        max_iter=30,
        tol=1e-4,
        class_weight={0: 1.0, 1: 1.4},
        n_jobs=-1,
        average=True,
        random_state=42,
    )
    model.fit(vectors, labels)

    model_payload = {
        "coef": model.coef_[0].astype(np.float64).tolist(),
        "intercept": float(model.intercept_[0]),
    }
    with open(MODEL_PATH, "w") as f:
        json.dump(model_payload, f)
    logger.info("train_model_done path=%s", MODEL_PATH)

def build_assets():
    """Process all downloaded files and train the runtime model."""
    # Download all necessary files
    logger.info("build_assets_start")
    download_dataset()
    download_auxiliary_files()
    
    logger.info("reference_dataset_load_start")
    with gzip.open("resources/references.json.gz", "rt") as f:
        data = json.load(f)
        
    n = len(data)  # 3,000,000
    logger.info("reference_dataset_load_done samples=%s", n)
    
    # Create NumPy arrays
    vectors = np.empty((n, 14), dtype=np.float32)
    labels = np.zeros(n, dtype=np.uint8)  # 0 = legit, 1 = fraud
    
    for i, item in enumerate(data):
        vectors[i] = item["vector"]
        labels[i] = 1 if item["label"] == "fraud" else 0
        if i and i % 250000 == 0:
            logger.info("vectorize_progress processed=%s", i)
        
    del data

    train_model(vectors, labels)
    
    # Clean up original large JSON files to save space
    os.remove("resources/references.json.gz")
    logger.info("build_assets_done samples=%s", n)

if __name__ == "__main__":
    build_assets()