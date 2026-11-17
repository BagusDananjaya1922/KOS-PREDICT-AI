from django.db import models


from django.db import models


class PredictionHistory(models.Model):
    AC_CHOICES = [
        ("ya", "Ada AC"),
        ("tidak", "Tidak ada AC"),
    ]

    jarak_km = models.FloatField()
    ac = models.CharField(
        max_length=10,
        choices=AC_CHOICES,
    )
    rating = models.FloatField()

    predicted_price = models.FloatField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Riwayat Prediksi"
        verbose_name_plural = "Riwayat Prediksi"

    def __str__(self):
        return f"Prediksi Rp{self.predicted_price:,.0f}"
# Create your models here.
