from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import TestCase

from .models import PredictionHistory
from .views import _parse_budget


class BudgetInputTests(TestCase):
    def test_budget_accepts_rupiah_thousands_separators(self):
        for value in ("800.000", "800000", "800 000"):
            with self.subTest(value=value):
                self.assertEqual(_parse_budget(value), 800000)

    def test_budget_rejects_invalid_characters_and_out_of_range_values(self):
        for value in ("80.000", "10.000.001", "800,000"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _parse_budget(value)


class DashboardStaticAssetsTests(TestCase):
    def test_dashboard_references_discoverable_static_assets(self):
        rendered = render_to_string("prediction/dashboard.html")

        self.assertIn(
            'href="/static/prediction/css/kosguss-theme.css"',
            rendered,
        )
        self.assertIn(
            'src="/static/prediction/js/kosguss-fx.js"',
            rendered,
        )
        self.assertIsNotNone(finders.find("prediction/css/kosguss-theme.css"))
        self.assertIsNotNone(finders.find("prediction/js/kosguss-fx.js"))

    def test_dashboard_uses_updated_branding_and_homepage_description(self):
        rendered = render_to_string("prediction/dashboard.html")

        self.assertIn("GusSearch Kost", rendered)
        self.assertIn("Prediksi Kost by Ai", rendered)
        self.assertIn("GusSearch - Prediksi Kost By Ai", rendered)
        self.assertIn("fasilitas AC, dan rating", rendered)
        self.assertNotIn("KosGuss AI", rendered)
        self.assertNotIn("Prediksi Kos Guss by AI", rendered)


class PredictionHistoryDeletionTests(TestCase):
    def test_post_deletes_all_history_records(self):
        PredictionHistory.objects.create(
            jarak_km=1.5, ac="ya", rating=4.0, predicted_price=850000,
        )
        PredictionHistory.objects.create(
            jarak_km=2.0, ac="tidak", rating=3.5, predicted_price=700000,
        )

        response = self.client.post("/history/delete/")

        self.assertRedirects(
            response,
            "/#riwayat",
            fetch_redirect_response=False,
        )
        self.assertEqual(PredictionHistory.objects.count(), 0)

    def test_get_does_not_delete_history(self):
        PredictionHistory.objects.create(
            jarak_km=1.5, ac="ya", rating=4.0, predicted_price=850000,
        )

        response = self.client.get("/history/delete/")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(PredictionHistory.objects.count(), 1)
