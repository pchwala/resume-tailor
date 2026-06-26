from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("applied/", views.applied, name="applied"),
    path("tailored/", views.tailored, name="tailored"),
    # actions (stubbed)
    path("tailor/", views.tailor, name="tailor"),
    path("tailored/<int:pk>/pdf/", views.pdf_download, name="pdf_download"),
]
