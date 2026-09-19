from django.urls import path

from .views import DashboardPageView, LoginPageView, VerifyPageView

urlpatterns = [
    path('', LoginPageView.as_view(), name='login-page'),
    path('dashboard/', DashboardPageView.as_view(), name='dashboard-page'),
    path('verify/<uuid:token>/', VerifyPageView.as_view(), name='verify-page'),
]
