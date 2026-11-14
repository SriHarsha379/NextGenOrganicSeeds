from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from django.urls import path
from .views import user_login, user_register, user_logout, reset_password
from . import views

urlpatterns = [
    path("login/", user_login, name="login"),
    path("register/", user_register, name="register"),
    path("logout/", user_logout, name="logout"),
    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('forgot-password/', auth_views.PasswordResetView.as_view(), name='forgot_password'),  # alias — old links still work
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('reset-password/<uidb64>/<token>/', reset_password, name='reset_password'),
    path('password_reset_done/', views.password_reset_done, name='password_reset_done'),
    path('unsubscribe/<str:token>/', views.unsubscribe, name='unsubscribe'),
]
