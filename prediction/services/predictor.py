
import json
from pathlib import Path

import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = BASE_DIR / "ml_models" / "kos_price_model.joblib"
METADATA_PATH = BASE_DIR / "ml_models" / "metadata.json"


def load_metadata():
    if not METADATA_PATH.exists():
        return {}

    with open(METADATA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def predict_price(jarak_km, ac, rating):
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Model belum tersedia. Jalankan training terlebih dahulu."
        )

    model = joblib.load(MODEL_PATH)

    input_data = pd.DataFrame([{
        "jarak_km": float(jarak_km),
        "ac": ac,
        "rating": float(rating),
    }])

    prediction = model.predict(input_data)[0]

    return max(0, round(float(prediction)))
