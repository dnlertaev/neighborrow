from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, LogoutView, MeView, RegisterView, VerifyEmailView

urlpatterns = [
    path('register', RegisterView.as_view()), path('verify-email', VerifyEmailView.as_view()),
    path('login', LoginView.as_view()), path('refresh', TokenRefreshView.as_view()),
    path('logout', LogoutView.as_view()), path('me', MeView.as_view()),
]
