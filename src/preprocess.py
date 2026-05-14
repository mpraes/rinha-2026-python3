import gzip
import json
import numpy as np
import requests
import os

def download_file(url, local_path):
    """Download a file from URL to local path if it doesn't already exist."""
    if os.path.exists(local_path):
        print(f"{os.path.basename(local_path)} already exists locally.")
        return

    print(f"Downloading {os.path.basename(local_path)}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"{os.path.basename(local_path)} downloaded successfully!")

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

def build_assets():
    """Process all downloaded files and convert to binary format."""
    # Download all necessary files
    download_dataset()
    download_auxiliary_files()
    
    print("Processing reference dataset...")
    with gzip.open("resources/references.json.gz", "rt") as f:
        data = json.load(f)
        
    n = len(data)  # 3,000,000
    
    # Create NumPy arrays
    vectors = np.zeros((n, 14), dtype=np.float32)
    labels = np.zeros(n, dtype=np.uint8)  # 0 = legit, 1 = fraud
    
    for i, item in enumerate(data):
        vectors[i] = item["vector"]
        labels[i] = 1 if item["label"] == "fraud" else 0
        
    # Save as binary files
    vectors.tofile("resources/vectors.bin")
    labels.tofile("resources/labels.bin")
    
    # Clean up original large JSON files to save space
    os.remove("resources/references.json.gz")
    print(f"Dataset processed successfully! {n} records saved to binary files.")
    print("Original JSON files cleaned up.")

if __name__ == "__main__":
    build_assets()