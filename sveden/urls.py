"""Адреса раздела «Сведения об образовательной организации» (CONTRACT.md, п. 4)."""

from django.urls import path

from . import views

app_name = "sveden"

urlpatterns = [
    path("", views.index, name="index"),
    path("common/", views.common, name="common"),
    path("struct/", views.struct, name="struct"),
    path("document/", views.document, name="document"),
    path("education/", views.education, name="education"),
    path("eduStandarts/", views.edu_standarts, name="eduStandarts"),
    path("managers/", views.managers, name="managers"),
    path("employees/", views.employees, name="employees"),
    path("objects/", views.objects, name="objects"),
    path("paid_edu/", views.paid_edu, name="paid_edu"),
    path("budget/", views.budget, name="budget"),
    path("vacant/", views.vacant, name="vacant"),
    path("grants/", views.grants, name="grants"),
    path("inter/", views.inter, name="inter"),
    path("catering/", views.catering, name="catering"),
]
