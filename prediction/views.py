import json
from pathlib import Path

import pandas as pd

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .models import PredictionHistory
from .services.ai_insight import TOPICS, AIInsightError, generate_insight
from .services.predictor import find_similar_kos, load_metadata, predict_price


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BASE_DIR / "data" / "kos_madiun.csv"


def load_dataset():
    df = pd.read_csv(DATASET_PATH)
    # Harga di CSV dalam ribuan rupiah -> ubah ke rupiah penuh.
    df["harga_rp"] = df["harga"] * 1000
    return df


def _group_mean(df, column, bins, labels):
    groups = pd.cut(df[column], bins=bins, labels=labels)
    result = df.groupby(groups, observed=True)["harga_rp"].agg(["mean", "count"])
    return {
        str(label): {"rata_rata": int(round(row["mean"])), "jumlah_kos": int(row["count"])}
        for label, row in result.iterrows()
    }


def dataset_summary(df):
    ac = df[df["ac"] == "ya"]
    non_ac = df[df["ac"] == "tidak"]
    cheapest = df.loc[df["harga_rp"].idxmin()]
    priciest = df.loc[df["harga_rp"].idxmax()]

    return {
        "jumlah_kos": int(len(df)),
        "harga_rata_rata": int(round(df["harga_rp"].mean())),
        "harga_tengah_median": int(round(df["harga_rp"].median())),
        "harga_termurah": int(df["harga_rp"].min()),
        "harga_termahal": int(df["harga_rp"].max()),
        "kos_termurah": str(cheapest["nama"]),
        "kos_termahal": str(priciest["nama"]),
        "rating_rata_rata": round(float(df["rating"].mean()), 1),
        "jarak_rata_rata_km": round(float(df["jarak_km"].mean()), 1),
        "ac": {
            "rata_rata_ber_ac": int(round(ac["harga_rp"].mean())),
            "jumlah_ber_ac": int(len(ac)),
            "rata_rata_tanpa_ac": int(round(non_ac["harga_rp"].mean())),
            "jumlah_tanpa_ac": int(len(non_ac)),
        },
        "korelasi_jarak_harga": round(float(df["jarak_km"].corr(df["harga_rp"])), 2),
        "korelasi_rating_harga": round(float(df["rating"].corr(df["harga_rp"])), 2),
        "harga_per_kelompok_jarak": _group_mean(
            df, "jarak_km", [0, 1.5, 3, 100],
            ["dekat (< 1,5 km)", "sedang (1,5 - 3 km)", "jauh (> 3 km)"],
        ),
        "harga_per_kelompok_rating": _group_mean(
            df, "rating", [0, 3.5, 4.2, 5],
            ["biasa (<= 3,5)", "baik (3,6 - 4,2)", "sangat baik (> 4,2)"],
        ),
    }


def _parse_budget(value):
    if not value or any(char not in "0123456789. " for char in value):
        raise ValueError

    digits = value.replace(".", "").replace(" ", "")
    if not digits:
        raise ValueError

    budget = int(digits)
    if budget < 100000 or budget > 10000000:
        raise ValueError
    return budget


def dashboard(request):
    df = load_dataset()
    summary = dataset_summary(df)
    metadata = load_metadata()

    # Rekomendasi kos berdasarkan budget pengguna.
    budget_input = request.GET.get("budget", "").strip()
    budget = None
    recommended_kos = []
    budget_error = ""

    if budget_input:
        try:
            budget = _parse_budget(budget_input)

            filtered_kos = df[df["harga_rp"] <= budget].copy()
            filtered_kos = filtered_kos.sort_values(
                by=["harga_rp", "jarak_km"],
                ascending=[True, True],
            )

            recommended_kos = [
                {
                    "nama": row.nama,
                    "harga": int(row.harga_rp),
                    "jarak": float(row.jarak_km),
                    "rating": float(row.rating),
                    "ac": row.ac,
                }
                for row in filtered_kos.itertuples()
            ]

        except (ValueError, TypeError):
            budget = None
            budget_error = "Masukkan budget antara Rp100.000 sampai Rp10.000.000."

    points = [
        {
            "nama": row.nama,
            "jarak": float(row.jarak_km),
            "rating": float(row.rating),
            "harga": int(row.harga_rp),
            "ac": row.ac,
        }
        for row in df.itertuples()
    ]

    latest_prediction = request.session.get("latest_prediction")
    price_range = None
    similar_kos = []
    if latest_prediction:
        margin = metadata.get("mae") or latest_prediction["predicted_price"] * 0.1
        price_range = {
            "min": max(0, round(latest_prediction["predicted_price"] - margin)),
            "max": round(latest_prediction["predicted_price"] + margin),
        }
        diff = latest_prediction["predicted_price"] - summary["harga_rata_rata"]
        latest_prediction = {
            **latest_prediction,
            "selisih": abs(round(diff)),
            "lebih_mahal": diff > 0,
        }

        similar_kos = find_similar_kos(
            latest_prediction["jarak_km"],
            latest_prediction["ac"],
            latest_prediction["rating"],
        )

        for kos in similar_kos:
            kos["selisih_harga"] = (
                kos["harga"] - latest_prediction["predicted_price"]
            )

    context = {
        "summary": summary,
        "metadata": metadata,
        "latest_prediction": latest_prediction,
        "price_range": price_range,
        "similar_kos": similar_kos,
        "budget": budget,
        "budget_input": budget_input,
        "recommended_kos": recommended_kos,
        "recommended_count": len(recommended_kos),
        "budget_error": budget_error,
        "history": PredictionHistory.objects.all()[:15],
        "total_predictions": PredictionHistory.objects.count(),
        "chart_data": {
            "points": points,
            "ac": [summary["ac"]["rata_rata_ber_ac"], summary["ac"]["rata_rata_tanpa_ac"]],
        },
    }
    return render(request, "prediction/dashboard.html", context)


@require_POST
def predict(request):
    try:
        jarak_km = float(request.POST.get("jarak_km", ""))
        rating = float(request.POST.get("rating", ""))
        ac = request.POST.get("ac", "")

        if not 0.1 <= jarak_km <= 20:
            raise ValueError("Jarak harus antara 0,1 sampai 20 km.")
        if not 0 <= rating <= 5:
            raise ValueError("Rating harus antara 0 sampai 5.")
        if ac not in ["ya", "tidak"]:
            raise ValueError("Pilihan fasilitas AC tidak valid.")

        predicted_price = predict_price(jarak_km, ac, rating)

        PredictionHistory.objects.create(
            jarak_km=jarak_km, ac=ac, rating=rating, predicted_price=predicted_price,
        )
        request.session["latest_prediction"] = {
            "jarak_km": jarak_km,
            "ac": ac,
            "rating": rating,
            "predicted_price": predicted_price,
        }
        messages.success(request, "Perkiraan harga berhasil dihitung!")

    except (ValueError, TypeError) as error:
        messages.error(request, str(error) or "Input tidak valid.")
    except FileNotFoundError as error:
        messages.error(request, str(error))

    return redirect(reverse("dashboard") + "#cek-harga")


@require_POST
def delete_history(request):
    deleted_count, _ = PredictionHistory.objects.all().delete()
    if deleted_count:
        messages.success(request, f"{deleted_count} riwayat prediksi berhasil dihapus.")
    else:
        messages.info(request, "Tidak ada riwayat prediksi untuk dihapus.")
    return redirect(reverse("dashboard") + "#riwayat")


@require_GET
def api_insight(request):
    topik = request.GET.get("topik", "")
    if topik not in TOPICS:
        return JsonResponse({"ok": False, "error": "Topik tidak dikenal."}, status=400)

    metadata = load_metadata()
    context = {
        "data_pasar": dataset_summary(load_dataset()),
        "model": {
            "nama_algoritma": metadata.get("model_name"),
            "mae_rupiah": round(metadata.get("mae", 0)),
            "rmse_rupiah": round(metadata.get("rmse", 0)),
            "r2": round(metadata.get("r2", 0), 3),
            "mae_validasi_silang": round(metadata.get("cross_validation_mae", 0)),
            "mae_tebakan_rata_rata_saja": round(metadata.get("baseline_dummy_mae", 0)),
            "jumlah_data_latih": metadata.get("training_rows"),
            "jumlah_data_uji": metadata.get("testing_rows"),
        },
    }

    if topik == "prediksi":
        latest = request.session.get("latest_prediction")
        if not latest:
            return JsonResponse(
                {"ok": False, "error": "Belum ada hasil prediksi untuk dijelaskan."}, status=400
            )
        context["input_pengguna"] = latest

    try:
        result = generate_insight(topik, context, refresh=request.GET.get("refresh") == "1")
    except AIInsightError as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=503)

    return JsonResponse({"ok": True, **result})


@require_POST
def api_simulate(request):
    latest = request.session.get("latest_prediction")

    if not latest:
        return JsonResponse(
            {"ok": False, "error": "Buat prediksi awal terlebih dahulu."},
            status=400,
        )

    try:
        jarak_km = float(request.POST.get("jarak_km", ""))
        rating = float(request.POST.get("rating", ""))
        ac = request.POST.get("ac", "")

        if not 0.1 <= jarak_km <= 20:
            raise ValueError("Jarak harus antara 0,1 sampai 20 km.")
        if not 0 <= rating <= 5:
            raise ValueError("Rating harus antara 0 sampai 5.")
        if ac not in ["ya", "tidak"]:
            raise ValueError("Pilihan fasilitas AC tidak valid.")

        simulated_price = predict_price(jarak_km, ac, rating)

        original_price = int(latest["predicted_price"])
        difference = simulated_price - original_price

        return JsonResponse({
            "ok": True,
            "original_price": original_price,
            "simulated_price": simulated_price,
            "difference": difference,
            "jarak_km": jarak_km,
            "ac": ac,
            "rating": rating,
        })

    except (ValueError, TypeError) as error:
        return JsonResponse(
            {"ok": False, "error": str(error) or "Input tidak valid."},
            status=400,
        )
    except FileNotFoundError as error:
        return JsonResponse(
            {"ok": False, "error": str(error)},
            status=503,
        )
