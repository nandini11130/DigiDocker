from django.urls import path

from .views import IssuerListView

urlpatterns = [
    path('', IssuerListView.as_view(), name='issuer-list'),
]
