import falcon
import json
import numpy as np
from datetime import datetime

# 1. Carregar Constantes de Normalização de forma estática
with open("resources/normalization.json", "r") as f:
    norm = json.load(f)
with open("resources/mcc_risk.json", "r") as f:
    mcc_risk_map = json.load(f)

# 2. Carregar datasets via mmap (O OS compartilha essa memória física entre as APIs!)
N_RECORDS = 3000000
X_ref = np.memmap("resources/vectors.bin", dtype=np.float32, mode='r', shape=(N_RECORDS, 14))
y_ref = np.memmap("resources/labels.bin", dtype=np.uint8, mode='r', shape=(N_RECORDS,))

def normalize_payload(payload):
    """Transform transaction payload JSON into a 14-dimension NumPy array of float32."""
    # --- PARSING E VETORIZAÇÃO ULTRA RÁPIDA ---
    tx = payload["transaction"]
    cust = payload["customer"]
    merch = payload["merchant"]
    term = payload["terminal"]
    last_tx = payload["last_transaction"]
    
    # Parsing de datas
    req_dt = datetime.fromisoformat(tx["requested_at"].replace("Z", "+00:00"))
    
    # Construção do vetor na exata ordem das regras
    v = np.empty(14, dtype=np.float32)
    
    v[0] = min(tx["amount"] / norm["max_amount"], 1.0)
    v[1] = min(tx["installments"] / norm["max_installments"], 1.0)
    v[2] = min((tx["amount"] / cust["avg_amount"]) / norm["amount_vs_avg_ratio"], 1.0)
    v[3] = req_dt.hour / 23.0
    v[4] = req_dt.weekday() / 6.0
    
    if last_tx is None:
        v[5] = -1.0
        v[6] = -1.0
    else:
        last_dt = datetime.fromisoformat(last_tx["timestamp"].replace("Z", "+00:00"))
        delta_min = (req_dt - last_dt).total_seconds() / 60.0
        v[5] = min(delta_min / norm["max_minutes"], 1.0)
        v[6] = min(last_tx["km_from_current"] / norm["max_km"], 1.0)
        
    v[7] = min(term["km_from_home"] / norm["max_km"], 1.0)
    v[8] = min(cust["tx_count_24h"] / norm["max_tx_count_24h"], 1.0)
    v[9] = 1.0 if term["is_online"] else 0.0
    v[10] = 1.0 if term["card_present"] else 0.0
    v[11] = 0.0 if merch["id"] in cust["known_merchants"] else 1.0
    v[12] = mcc_risk_map.get(merch["mcc"], 0.5)
    v[13] = min(merch["avg_amount"] / norm["max_merchant_avg_amount"], 1.0)
    
    return v

FRAUD_THRESHOLD = 0.6
K_NEIGHBORS = 5

def knn_search(v):
    """Find K nearest neighbors and compute fraud score.

    Uses vectorized squared Euclidean distance via np.einsum and
    np.argpartition for O(n) selection of the K smallest distances.

    Returns (approved, fraud_score).
    """
    # Squared Euclidean: d^2 = sum((A_i - B_i)^2) across 14 dims per row
    # einsum('ij,ij->i') computes row-wise dot product of diff with itself
    diff = X_ref - v
    dists_sq = np.einsum('ij,ij->i', diff, diff)

    # argpartition is O(n) — partial sort that places the K smallest
    # elements in the first K positions (unsorted among themselves)
    nearest_indices = np.argpartition(dists_sq, K_NEIGHBORS)[:K_NEIGHBORS]

    # Fraud score = fraction of fraudulent neighbors
    frauds_count = np.sum(y_ref[nearest_indices])
    fraud_score = frauds_count / K_NEIGHBORS
    approved = fraud_score < FRAUD_THRESHOLD

    return approved, fraud_score

class FraudScoreResource:
    def on_post(self, req, resp):
        try:
            raw_payload = req.bounded_stream.read()
            payload = json.loads(raw_payload)

            v = normalize_payload(payload)
            approved, fraud_score = knn_search(v)

            resp.status = falcon.HTTP_200
            resp.text = json.dumps({"approved": bool(approved), "fraud_score": float(fraud_score)})

        except Exception:
            resp.status = falcon.HTTP_200
            resp.text = '{"approved": true, "fraud_score": 0.0}'

class ReadyResource:
    def on_get(self, req, resp):
        resp.status = falcon.HTTP_200
        resp.text = '{"status": "ready"}'

# Inicialização do App Falcon
app = falcon.App()
app.add_route("/ready", ReadyResource())
app.add_route("/fraud-score", FraudScoreResource())