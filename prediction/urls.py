from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("predict/", views.predict, name="predict"),
    path("history/delete/", views.delete_history, name="delete_history"),
    path("api/insight/", views.api_insight, name="api_insight"),
    path("api/simulate/", views.api_simulate, name="api_simulate"),
]
# bagus ganteng dewe sak magetan