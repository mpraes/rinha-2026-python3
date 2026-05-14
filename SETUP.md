# Setup Instructions

This project requires Python 3.12+ with pip and virtual environment support. If you're on a Debian/Ubuntu system, you may need to install additional packages:

```bash
sudo apt install python3-venv python3-pip -y
```

Then create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
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