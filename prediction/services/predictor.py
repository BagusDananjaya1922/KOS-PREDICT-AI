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


def find_similar_kos(jarak_km, ac, rating, limit=3):
    dataset_path = BASE_DIR / "data" / "kos_madiun.csv"

    if not dataset_path.exists():
        return []

    df = pd.read_csv(dataset_path)

    df["skor_jarak"] = (
        abs(df["jarak_km"] - float(jarak_km)) / 20
    )

    df["skor_rating"] = (
        abs(df["rating"] - float(rating)) / 5
    )

    df["skor_ac"] = (
        df["ac"] != ac
    ).astype(float)

    df["skor_total"] = (
        df["skor_jarak"] * 0.4
        + df["skor_rating"] * 0.3
        + df["skor_ac"] * 0.3
    )

    df = df.sort_values("skor_total")

    results = []

    for row in df.head(limit).itertuples():
        results.append({
            "nama": row.nama,
            "harga": int(row.harga * 1000),
            "jarak_km": float(row.jarak_km),
            "ac": row.ac,
            "rating": float(row.rating),
            "skor": round((1 - row.skor_total) * 100, 1),
        })

    return results
