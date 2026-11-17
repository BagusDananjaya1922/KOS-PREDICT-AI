import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression, Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import (
    KFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# ==========================================
# 1. LOKASI FILE
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "kos_madiun.csv"
MODEL_DIR = BASE_DIR / "ml_models"

MODEL_DIR.mkdir(exist_ok=True)

# ==========================================
# 2. MEMBACA DATASET
# ==========================================

df = pd.read_csv(DATA_PATH)

FEATURES = ["jarak_km", "ac", "rating"]
TARGET = df["harga"] * 1000

X = df[FEATURES]
y = TARGET

# ==========================================
# 3. MEMBAGI DATA TRAINING DAN TESTING
# ==========================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
)

# ==========================================
# 4. PREPROCESSING PIPELINE
# ==========================================

numeric_features = ["jarak_km", "rating"]
categorical_features = ["ac"]

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            StandardScaler(),
            numeric_features,
        ),
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features,
        ),
    ]
)

# ==========================================
# 5. KANDIDAT ALGORITMA MODEL
# ==========================================

models = {
    "Huber Regressor (Robust)": HuberRegressor(epsilon=1.35, max_iter=500),
    "Ridge Regression": Ridge(alpha=5.0),
    "Random Forest": RandomForestRegressor(
        n_estimators=150,
        max_depth=3,
        min_samples_split=4,
        random_state=42,
    ),
    "Gradient Boosting": GradientBoostingRegressor(
        n_estimators=60,
        max_depth=2,
        learning_rate=0.08,
        random_state=42,
    ),
    "Linear Regression": LinearRegression(),
}

baseline_model = DummyRegressor(strategy="mean")

# ==========================================
# 6. CROSS VALIDATION & BENCHMARKING
# ==========================================

cv = KFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

# Evaluasi baseline dummy sebagai acuan
dummy_pipe = Pipeline([("preprocessor", preprocessor), ("model", baseline_model)])
dummy_scores = cross_val_score(
    dummy_pipe, X_train, y_train, cv=cv, scoring="neg_mean_absolute_error", n_jobs=-1
)
dummy_mae = -dummy_scores.mean()

print("\n====================================")
print("HASIL PERBANDINGAN MODEL (CV MAE)")
print("====================================")
print(f"Dummy Baseline (Acuan) : Rp{dummy_mae:,.0f}")

results = {}

for name, algorithm in models.items():
    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", algorithm),
        ]
    )

    scores = cross_val_score(
        pipeline,
        X_train,
        y_train,
        cv=cv,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
    )

    mean_mae = -scores.mean()
    results[name] = {
        "pipeline": pipeline,
        "cv_mae": mean_mae,
    }
    print(f"{name:26s}: Rp{mean_mae:,.0f}")

# ==========================================
# 7. MEMILIH MODEL TERBAIK DARI KANDIDAT
# ==========================================

best_name = min(
    results,
    key=lambda name: results[name]["cv_mae"],
)

best_pipeline = results[best_name]["pipeline"]

print("\n====================================")
print("MODEL TERPILIH")
print("====================================")
print("Nama model:", best_name)

# ==========================================
# 8. TRAINING MODEL TERPILIH
# ==========================================

best_pipeline.fit(X_train, y_train)

# ==========================================
# 9. EVALUASI DATA TESTING
# ==========================================

predictions = best_pipeline.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
rmse = np.sqrt(mean_squared_error(y_test, predictions))
r2 = r2_score(y_test, predictions)

print("\n====================================")
print("EVALUASI MODEL (TEST SET)")
print("====================================")
print(f"MAE  : Rp{mae:,.0f}")
print(f"RMSE : Rp{rmse:,.0f}")
print(f"R2   : {r2:.4f}")

# ==========================================
# 10. MENYIMPAN MODEL & METADATA
# ==========================================

model_path = MODEL_DIR / "kos_price_model.joblib"
joblib.dump(best_pipeline, model_path)

metadata = {
    "model_name": best_name,
    "features": FEATURES,
    "target": "harga",
    "currency": "IDR",
    "price_unit_assumption": (
        "Nilai harga pada CSV diasumsikan dalam ribuan rupiah per bulan."
    ),
    "dataset_rows": int(len(df)),
    "training_rows": int(len(X_train)),
    "testing_rows": int(len(X_test)),
    "mae": float(mae),
    "rmse": float(rmse),
    "r2": float(r2),
    "cross_validation_mae": float(results[best_name]["cv_mae"]),
    "baseline_dummy_mae": float(dummy_mae),
    "model_candidates": {
        k: float(v["cv_mae"]) for k, v in results.items()
    },
}

metadata_path = MODEL_DIR / "metadata.json"
with open(metadata_path, "w") as file:
    json.dump(metadata, file, indent=4)

print("\n====================================")
print("TRAINING SELESAI")
print("====================================")
print("Model tersimpan   :", model_path)
print("Metadata tersimpan:", metadata_path)
