
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("predict/", views.predict, name="predict"),
    path("api/insight/", views.api_insight, name="api_insight"),
]
