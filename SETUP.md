# Setup Instructions

This project requires Python 3.12+ and uv for dependency management. If you're on Debian/Ubuntu:

```bash
sudo apt install python3-venv -y
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then create the virtual environment and sync dependencies:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync --frozen --no-dev
```

After setting up the environment, you can run the preprocessing script:

```bash
python src/preprocess.py
```

This will:
1. Download the reference dataset (references.json.gz) from the Rinha de Backend 2026 repository
2. Download auxiliary files (mcc_risk.json, normalization.json)
3. Convert the JSON data to binary format (vectors.bin, labels.bin)
4. Clean up the original large JSON files to save space