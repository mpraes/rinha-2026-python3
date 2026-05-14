import falcon.asgi
import json
import logging
import math
import os
import time

try:
    import orjson
except Exception:  # pragma: no cover
    orjson = None

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "WARNING").upper(), logging.WARNING),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("fraud-api")
LOG_EACH_REQUEST = os.getenv("APP_LOG_EACH_REQUEST", "0") == "1"
DEBUG_TIMINGS = os.getenv("APP_DEBUG_TIMINGS", "0") == "1"

if orjson is not None:
    def _loads(raw):
        return orjson.loads(raw)

    def _dumps(payload):
        return orjson.dumps(payload)
else:
    def _loads(raw):
        return json.loads(raw)

    def _dumps(payload):
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

with open("resources/normalization.json", "r") as f:
    norm = json.load(f)
with open("resources/mcc_risk.json", "r") as f:
    mcc_risk_map = json.load(f)

logger.info("loading_runtime_model path=resources/model.json")
with open("resources/model.json", "rb") as f:
    model_payload = _loads(f.read())
MODEL_COEF = tuple(float(v) for v in model_payload["coef"])
MODEL_INTERCEPT = float(model_payload["intercept"])
logger.info("runtime_model_loaded")

INV_MAX_AMOUNT = 1.0 / float(norm["max_amount"])
INV_MAX_INSTALLMENTS = 1.0 / float(norm["max_installments"])
INV_AMOUNT_VS_AVG_RATIO = 1.0 / float(norm["amount_vs_avg_ratio"])
INV_MAX_MINUTES = 1.0 / float(norm["max_minutes"])
INV_MAX_KM = 1.0 / float(norm["max_km"])
INV_MAX_TX_COUNT_24H = 1.0 / float(norm["max_tx_count_24h"])
INV_MAX_MERCHANT_AVG_AMOUNT = 1.0 / float(norm["max_merchant_avg_amount"])


def _clamp01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _parse_iso_ymdhm(ts):
    year = int(ts[0:4])
    month = int(ts[5:7])
    day = int(ts[8:10])
    hour = int(ts[11:13])
    minute = int(ts[14:16])
    return year, month, day, hour, minute


def _days_from_civil(year, month, day):
    y = year - (1 if month <= 2 else 0)
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - (era * 400)
    mp = month + (9 if month <= 2 else -3)
    doy = ((153 * mp) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _epoch_minutes_from_iso(ts):
    year, month, day, hour, minute = _parse_iso_ymdhm(ts)
    return _days_from_civil(year, month, day) * 1440 + hour * 60 + minute


def _weekday_from_days(days_since_epoch):
    return (days_since_epoch + 3) % 7


def _safe_ratio(numerator, denominator):
    if denominator <= 0:
        return 1e12
    return numerator / denominator


def score_payload(payload):
    tx = payload["transaction"]
    cust = payload["customer"]
    merch = payload["merchant"]
    term = payload["terminal"]
    last_tx = payload["last_transaction"]

    amount = float(tx["amount"])
    req_ts = tx["requested_at"]
    y, m, d, req_hour, _ = _parse_iso_ymdhm(req_ts)
    req_days = _days_from_civil(y, m, d)
    req_weekday = _weekday_from_days(req_days)
    req_min = req_days * 1440 + req_hour * 60 + int(req_ts[14:16])

    f0 = _clamp01(amount * INV_MAX_AMOUNT)
    f1 = _clamp01(float(tx["installments"]) * INV_MAX_INSTALLMENTS)
    f2 = _clamp01(_safe_ratio(amount, float(cust["avg_amount"])) * INV_AMOUNT_VS_AVG_RATIO)
    f3 = req_hour / 23.0
    f4 = req_weekday / 6.0

    if last_tx is None:
        f5 = -1.0
        f6 = -1.0
    else:
        last_min = _epoch_minutes_from_iso(last_tx["timestamp"])
        delta_min = req_min - last_min
        f5 = _clamp01(float(delta_min) * INV_MAX_MINUTES)
        f6 = _clamp01(float(last_tx["km_from_current"]) * INV_MAX_KM)

    f7 = _clamp01(float(term["km_from_home"]) * INV_MAX_KM)
    f8 = _clamp01(float(cust["tx_count_24h"]) * INV_MAX_TX_COUNT_24H)
    f9 = 1.0 if term["is_online"] else 0.0
    f10 = 1.0 if term["card_present"] else 0.0

    known = cust["known_merchants"]
    f11 = 0.0 if merch["id"] in (known if isinstance(known, set) else set(known)) else 1.0

    mcc_key = str(merch["mcc"])
    f12 = mcc_risk_map.get(mcc_key, 0.5)

    f13 = _clamp01(float(merch["avg_amount"]) * INV_MAX_MERCHANT_AVG_AMOUNT)

    f14 = f0 * f2       # amount × amount_vs_avg
    f15 = f0 * f9       # amount × is_online
    f16 = f0 * f7       # amount × km_from_home
    f17 = f3 * f7       # hour × km_from_home
    f18 = f2 * f8       # amount_vs_avg × tx_count_24h
    f19 = f9 * f10      # is_online × card_present
    f20 = f7 * f9       # km_from_home × is_online
    f21 = f0 * max(f5, 0.0)  # amount × minutes_since_last_tx

    c = MODEL_COEF
    linear = (
        MODEL_INTERCEPT
        + c[0] * f0 + c[1] * f1 + c[2] * f2 + c[3] * f3
        + c[4] * f4 + c[5] * f5 + c[6] * f6 + c[7] * f7
        + c[8] * f8 + c[9] * f9 + c[10] * f10 + c[11] * f11
        + c[12] * f12 + c[13] * f13
        + c[14] * f14 + c[15] * f15 + c[16] * f16 + c[17] * f17
        + c[18] * f18 + c[19] * f19 + c[20] * f20 + c[21] * f21
    )

    if linear >= 0.0:
        z = math.exp(-linear)
        fraud_score = 1.0 / (1.0 + z)
    else:
        z = math.exp(linear)
        fraud_score = z / (1.0 + z)
    approved = fraud_score < FRAUD_THRESHOLD
    return approved, fraud_score

FRAUD_THRESHOLD = 0.6
threshold_env = os.getenv("FRAUD_THRESHOLD")
if threshold_env:
    FRAUD_THRESHOLD = float(threshold_env)

class FraudScoreResource:
    async def on_post(self, req, resp):
        started_at = time.perf_counter()
        try:
            raw_payload = await req.bounded_stream.read()
            payload = _loads(raw_payload)
            tx_id = payload.get("id", "unknown")

            approved, fraud_score = score_payload(payload)
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0

            if LOG_EACH_REQUEST:
                logger.info(
                    "fraud_score_request tx_id=%s approved=%s fraud_score=%.6f elapsed_ms=%.3f",
                    tx_id,
                    approved,
                    fraud_score,
                    elapsed_ms,
                )
            elif DEBUG_TIMINGS and elapsed_ms > 10.0:
                logger.warning(
                    "fraud_score_request_slow tx_id=%s elapsed_ms=%.3f",
                    tx_id,
                    elapsed_ms,
                )

            resp.status = falcon.HTTP_200
            resp.data = _dumps({"approved": bool(approved), "fraud_score": float(fraud_score)})

        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            logger.exception("fraud_score_request_failed elapsed_ms=%.3f", elapsed_ms)
            resp.status = falcon.HTTP_200
            resp.data = b'{"approved":true,"fraud_score":0.0}'

class ReadyResource:
    async def on_get(self, req, resp):
        resp.status = falcon.HTTP_200
        resp.text = '{"status": "ready"}'

app = falcon.asgi.App()
app.add_route("/ready", ReadyResource())
app.add_route("/fraud-score", FraudScoreResource())
