"""Layanan penjelasan berbasis AI (Groq) untuk grafik & hasil prediksi."""

import hashlib
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
CACHE_SECONDS = 60 * 30  # simpan jawaban 30 menit agar hemat kuota


class AIInsightError(Exception):
    """Error yang pesannya aman ditampilkan ke pengguna."""


SYSTEM_PROMPT = (
    "Kamu adalah asisten analis properti untuk aplikasi 'KosGuss AI' "
    "(Prediksi Kos Guss by AI) di Kota Madiun. Jelaskan data kepada orang awam "
    "(mahasiswa / pencari kos) dalam Bahasa Indonesia yang santai, jelas, dan jujur. "
    "Aturan: pakai HANYA angka dari data yang diberikan, jangan mengarang. "
    "Tulis harga dalam format Rupiah (contoh: Rp1.050.000). "
    "Maksimal 110 kata. Format: 1 kalimat pembuka, lalu 2-4 poin yang masing-masing "
    "diawali '- '. Jangan pakai markdown lain (tanpa **, #, atau tabel)."
)

TOPICS = {
    "ringkasan": (
        "Berikan gambaran umum pasar kos di Madiun dari ringkasan data ini: "
        "kisaran harga, harga umum, dan hal paling menarik untuk pencari kos."
    ),
    "grafik_ac": (
        "Jelaskan grafik perbandingan rata-rata harga kos ber-AC vs tanpa AC. "
        "Apakah AC benar-benar membuat harga lebih mahal di data ini? Sebutkan selisihnya."
    ),
    "grafik_jarak": (
        "Jelaskan grafik sebaran harga kos terhadap jarak ke pusat kota. Pakai nilai "
        "korelasi dan rata-rata harga per kelompok jarak. Terangkan arti korelasi "
        "dengan bahasa sangat sederhana."
    ),
    "grafik_rating": (
        "Jelaskan grafik hubungan rating kos dengan harga. Pakai nilai korelasi dan "
        "rata-rata harga per kelompok rating. Apakah kos dengan rating tinggi pasti mahal?"
    ),
    "model": (
        "Jelaskan seberapa bisa dipercaya model prediksi ini untuk orang awam. Terangkan "
        "arti MAE (rata-rata meleset berapa rupiah) dan R² dengan bahasa sederhana, akui "
        "keterbatasannya dengan jujur (data sedikit), lalu beri saran agar lebih akurat."
    ),
    "prediksi": (
        "Jelaskan hasil prediksi harga kos untuk input pengguna ini. Bandingkan dengan "
        "rata-rata pasar dan kelompok yang mirip (jarak/AC/rating), sebutkan rentang "
        "wajar memakai MAE model, lalu beri 1 tips praktis untuk pencari kos."
    ),
}


def generate_insight(topik, context, refresh=False):
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise AIInsightError("GROQ_API_KEY belum diatur di file .env.")

    model = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")
    context_json = json.dumps(context, ensure_ascii=False, default=str)
    cache_key = "ai:" + hashlib.sha256(
        f"{model}|{topik}|{context_json}".encode("utf-8")
    ).hexdigest()

    if not refresh:
        cached = cache.get(cache_key)
        if cached:
            return {**cached, "cached": True}

    payload = {
        "model": model,
        "temperature": 0.4,
        "max_completion_tokens": 1200,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"{TOPICS[topik]}\n\nData (JSON):\n{context_json}",
            },
        ],
    }
    if model.startswith("openai/gpt-oss"):
        # Model "reasoning": cukup berpikir singkat agar cepat & hemat token.
        payload["reasoning_effort"] = "low"
        payload["include_reasoning"] = False

    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "KosGussAI/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "ignore")[:300]
        if error.code == 401:
            raise AIInsightError("API key Groq tidak valid atau sudah dicabut.") from error
        if error.code == 429:
            raise AIInsightError("Batas pemakaian Groq tercapai, coba lagi sebentar.") from error
        raise AIInsightError(f"Groq menolak permintaan (HTTP {error.code}): {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise AIInsightError("Tidak bisa terhubung ke Groq. Periksa koneksi internet.") from error

    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as error:
        raise AIInsightError("Respons dari Groq tidak terduga.") from error

    result = {
        "text": text,
        "model": model,
        "generated_at": timezone.localtime().strftime("%d %b %Y, %H:%M"),
    }
    cache.set(cache_key, result, CACHE_SECONDS)
    return {**result, "cached": False}
