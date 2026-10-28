"""Адреса публичной части сайта (имена неизменны — CONTRACT.md, п. 4)."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("obuchenie/", views.program_list, name="program_list"),
    path("obuchenie/<slug:slug>/", views.program_detail, name="program_detail"),
    path("kontakty/", views.contacts, name="contacts"),
    path("zayavka/", views.lead_create, name="lead_create"),
    path("zayavka/spasibo/", views.lead_success, name="lead_success"),
    path("politika/", views.privacy, name="privacy"),
    path("soglasie/", views.consent, name="consent"),
]
