from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from django.urls import path
from .views import user_login, user_register, user_logout, forgot_password, reset_password
from . import views

urlpatterns = [
    path("login/", user_login, name="login"),
    path("register/", user_register, name="register"),
    path("logout/", user_logout, name="logout"),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    # path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    # path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    # path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    # path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', reset_password, name='reset_password'),
    path('password_reset_done/', views.password_reset_done, name='password_reset_done'),
]